#!/usr/bin/env python3
"""
X (Twitter) Commenter Bot - Adaptive Columns + In-Browser Login Confirm

This script automates X (Twitter) commenting using Selenium with a hybrid interactive login.
Enhancements:
- ADAPTS to varying Excel column names (e.g., 'postUrl', 'Generated comment ') and normalizes to URL + generated_comment.
- In-browser floating panel with "I'm logged in" button (no terminal ENTER needed).
- Smart filtering: skips rows already marked 'Y' in "Commented (Y/N)" and updates the sheet.
- Two-space indentation per user preference.

Author: AI Assistant
Version: 1.2
Python: >=3.10
"""

import argparse
import logging
import os
import pandas as pd
import random
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import chromedriver_autoinstaller
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
  TimeoutException,
  NoSuchElementException,
  StaleElementReferenceException,
  WebDriverException
)


class XCommentBot:
  """
  Automates X (Twitter) commenting with adaptive Excel parsing and a no-terminal login flow.
  """

  def __init__(self, delay: float = 2.0, profile_path: str = None):
    self.delay = delay
    self.profile_path = profile_path
    self.driver = None
    self.wait = None
    self.main_window = None
    self.results: List[Dict] = []
    self.original_df: Optional[pd.DataFrame] = None
    self.sheet_path: Optional[str] = None
    self.setup_logging()

  def setup_logging(self):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"x_commenter_{timestamp}.log"
    logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s - %(levelname)s - %(message)s",
      handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, mode="w")
      ]
    )
    self.logger = logging.getLogger(__name__)
    self.logger.info(f"X Commenter Bot initialized. Log file: {log_file}")

  def setup_chrome_driver(self) -> webdriver.Chrome:
    self.logger.info("Setting up Chrome WebDriver...")
    driver_path = chromedriver_autoinstaller.install()
    self.logger.info(f"ChromeDriver installed at: {driver_path}")
    chrome_options = Options()
    chrome_options.add_argument("--no-headless")
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    if self.profile_path:
      chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
    else:
      temp_dir = tempfile.mkdtemp()
      chrome_options.add_argument(f"--user-data-dir={temp_dir}")
      self.logger.info(f"Using temporary profile directory: {temp_dir}")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    service = Service(driver_path)
    self.driver = webdriver.Chrome(service=service, options=chrome_options)
    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    self.wait = WebDriverWait(self.driver, 20)
    self.logger.info("Chrome WebDriver setup completed successfully")
    return self.driver

  def navigate_to_login(self):
    self.logger.info("Navigating to X login page...")
    self.driver.get("https://x.com/i/flow/login")
    self.main_window = self.driver.current_window_handle
    self.logger.info("X login page loaded")

  def wait_for_manual_login(self):
    # Delegate to UI-based flow so no terminal interaction is required
    return self.wait_for_manual_login_ui()

  
  def wait_for_manual_login_ui(self) -> bool:
    """
    Floating panel with an "I'm logged in" button.
    Keeps the panel visible across redirects by re-injecting it if it disappears.
    """
    try:
      self.logger.info("=" * 60)
      self.logger.info("LOGIN FLOW")
      self.logger.info("1) Log in on X in the opened Chrome window.")
      self.logger.info("2) Click the floating 'I'm logged in' button to continue.")
      self.logger.info("=" * 60)

      # Initial overlay
      self._inject_overlay_panel()

      start = time.time()
      timeout_seconds = 15 * 60  # 15 minutes
      last_log = 0
      last_url = ""

      while True:
        # Re-inject overlay if it disappeared during navigation/refresh
        try:
          present = self.driver.execute_script("return !!document.getElementById('xbot-login-overlay');")
        except Exception:
          present = True  # If JS failed, don't spam reinjection this tick

        try:
          current_url = self.driver.current_url
        except Exception:
          current_url = last_url

        if not present or current_url != last_url:
          try:
            self._inject_overlay_panel()
          except Exception:
            pass
          last_url = current_url

        # LocalStorage flag from the button
        try:
          flag = self.driver.execute_script("return window.localStorage.getItem('xbot_login_ok');")
        except Exception:
          flag = None

        if flag == "1":
          self.logger.info("Login confirmed via UI button.")
          try:
            self.driver.execute_script("window.localStorage.removeItem('xbot_login_ok');")
          except Exception:
            pass
          try:
            self.driver.execute_script("var el = document.getElementById('xbot-login-overlay'); if (el) { el.remove(); }")
          except Exception:
            pass
          break

        # Heuristic auto-confirmation
        if self.confirm_login():
          self.logger.info("Login auto-confirmed via page indicators.")
          try:
            self.driver.execute_script("var el = document.getElementById('xbot-login-overlay'); if (el) { el.remove(); }")
          except Exception:
            pass
          break

        if time.time() - start > timeout_seconds:
          self.logger.error("Login wait timed out after 15 minutes.")
          raise TimeoutException("Login not confirmed within timeout.")

        if time.time() - last_log > 10:
          self.logger.info("Waiting for login confirmation... (click the overlay button when ready)")
          last_log = time.time()

        time.sleep(1.0)

      return True

    except Exception as e:
      self.logger.error(f"Error during UI login wait: {str(e)}")
      return False

  def _inject_overlay_panel(self):
    """Injects a fixed overlay with a 'I'm logged in' button into the page."""
    try:
      self.driver.execute_script("""
        (function(){
          if (document.getElementById('xbot-login-overlay')) { return; }
          var wrap = document.createElement('div');
          wrap.id = 'xbot-login-overlay';
          wrap.style.position = 'fixed';
          wrap.style.right = '20px';
          wrap.style.bottom = '20px';
          wrap.style.zIndex = '999999';
          wrap.style.background = 'rgba(20,20,20,0.92)';
          wrap.style.color = '#fff';
          wrap.style.padding = '16px';
          wrap.style.borderRadius = '16px';
          wrap.style.boxShadow = '0 8px 24px rgba(0,0,0,0.35)';
          wrap.style.maxWidth = '320px';
          wrap.style.fontFamily = 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif';

          var title = document.createElement('div');
          title.textContent = 'X Comment Bot';
          title.style.fontSize = '16px';
          title.style.fontWeight = '600';
          title.style.marginBottom = '8px';

          var msg = document.createElement('div');
          msg.textContent = 'Log in to X in this window, then click the button below to continue.';
          msg.style.fontSize = '13px';
          msg.style.opacity = '0.9';
          msg.style.marginBottom = '12px';

          var bar = document.createElement('div');
          bar.style.display = 'flex';
          bar.style.gap = '8px';

          var btn = document.createElement('button');
          btn.textContent = "I'm logged in";
          btn.style.flex = '1';
          btn.style.padding = '10px 12px';
          btn.style.borderRadius = '12px';
          btn.style.border = 'none';
          btn.style.cursor = 'pointer';
          btn.style.fontWeight = '600';
          btn.style.fontSize = '14px';

          // Minimal styling to avoid detection heuristics.
          btn.addEventListener('click', function(){
            try {
              window.localStorage.setItem('xbot_login_ok', '1');
            } catch(e){}
            var el = document.getElementById('xbot-login-overlay');
            if (el) { el.remove(); }
          }, { once: true });

          var cancel = document.createElement('button');
          cancel.textContent = 'Hide';
          cancel.style.padding = '10px 12px';
          cancel.style.borderRadius = '12px';
          cancel.style.border = '1px solid rgba(255,255,255,0.25)';
          cancel.style.cursor = 'pointer';
          cancel.style.background = 'transparent';
          cancel.style.color = '#fff';

          cancel.addEventListener('click', function(){
            var el = document.getElementById('xbot-login-overlay');
            if (el) { el.remove(); }
          }, { once: true });

          bar.appendChild(btn);
          bar.appendChild(cancel);
          wrap.appendChild(title);
          wrap.appendChild(msg);
          wrap.appendChild(bar);
          document.documentElement.appendChild(wrap);
        })();
      """)
      self.logger.info("Injected login confirmation overlay into the page.")
    except Exception as e:
      self.logger.warning(f"Could not inject overlay panel: {e}")

  def confirm_login(self) -> bool:
    self.logger.info("Confirming login status...")
    try:
      login_indicators = [
        (By.CSS_SELECTOR, "[data-testid='SideNav_AccountSwitcher_Button']"),
        (By.CSS_SELECTOR, "[data-testid='AppTabBar_Profile_Link']"),
        (By.CSS_SELECTOR, "[aria-label='Profile']"),
        (By.CSS_SELECTOR, "[data-testid='primaryColumn']")
      ]
      for selector_type, selector in login_indicators:
        try:
          element = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((selector_type, selector))
          )
          if element:
            self.logger.info(f"Login confirmed via element: {selector}")
            return True
        except TimeoutException:
          continue
      current_url = self.driver.current_url
      if "/home" in current_url or ("x.com" in current_url and "/login" not in current_url):
        self.logger.info(f"Login confirmed via URL pattern: {current_url}")
        return True
      return False
    except Exception as e:
      self.logger.error(f"Error during login confirmation: {str(e)}")
      return False

  @staticmethod
  def _normalize(col: str) -> str:
    if col is None:
      return ""
    return (
      str(col)
      .strip()
      .lower()
      .replace("  ", " ")
      .replace(" ", "_")
      .replace("-", "_")
    )

  def _detect_column(self, norm_cols: List[str], raw_cols: List[str], want: str) -> Optional[str]:
    """
    Detect a column for 'url' or 'comment' by heuristics.
    Returns the RAW column name to use.
    """
    candidates = []
    for norm, raw in zip(norm_cols, raw_cols):
      if want == "url":
        if norm in ("url", "posturl", "tweet_url", "link"):
          candidates.append(raw)
        elif "url" in norm and ("post" in norm or "tweet" in norm or norm == "url"):
          candidates.append(raw)
      if want == "comment":
        if norm in ("generated_comment", "comment", "reply", "comment_text", "generatedcomment"):
          candidates.append(raw)
        elif "comment" in norm:
          candidates.append(raw)
    if candidates:
      return candidates[0]
    return None

  
  def _resolve_sheet_path(self, sheet_path: str) -> Path:
    """
    Resolve the sheet path robustly:
    - Strip quotes/whitespace and file:// prefix
    - Expand ~
    - If relative, make absolute from CWD
    - If not found, try alongside this script
    - If still not found, try case-insensitive match in CWD
    """
    sp = str(sheet_path).strip().strip('"').strip("'")
    if sp.startswith("file://"):
      sp = sp.replace("file://", "", 1)

    p = Path(sp).expanduser()
    if not p.is_absolute():
      p = Path.cwd() / p

    if p.exists():
      return p

    # Try alongside script
    try:
      here = Path(__file__).parent
      alt = here / p.name
      if alt.exists():
        return alt
    except Exception:
      pass

    # Case-insensitive search in CWD
    try:
      candidates = [c for c in Path.cwd().glob("*") if c.name.lower() == p.name.lower()]
      if candidates:
        return candidates[0]
    except Exception:
      pass

    return p

  def load_spreadsheet(self, sheet_path: str) -> pd.DataFrame:
    self.logger.info(f"Loading Excel spreadsheet: {sheet_path}")
    resolved = self._resolve_sheet_path(sheet_path)
    self.sheet_path = str(resolved)
    self.logger.info(f"Resolved sheet path: {self.sheet_path}")
    if not resolved.exists():
      cwd = Path.cwd()
      self.logger.error(f"Excel file not found. CWD: {cwd}")
      raise FileNotFoundError(f"Excel file not found at: {resolved}")
    try:
      df = pd.read_excel(self.sheet_path, engine="openpyxl")
      self.original_df = df.copy()
    except Exception as e:
      self.logger.error(f"pandas.read_excel failed: {repr(e)}")
      # Fallback: try openpyxl directly for first sheet
      try:
        import openpyxl
        wb = openpyxl.load_workbook(self.sheet_path, data_only=True, read_only=True)
        ws = wb.active
        rows = list(ws.values)
        import pandas as _pd
        df = _pd.DataFrame(rows[1:], columns=[str(c) for c in rows[0]])
        self.original_df = df.copy()
      except Exception as e2:
        self.logger.error(f"openpyxl fallback failed: {repr(e2)}")
        raise ValueError(f"Error reading Excel file after fallbacks: {e2}")

    # Normalize column names and build mapping
    raw_cols = list(df.columns)
    norm_cols = [self._normalize(c) for c in raw_cols]
    self.logger.info(f"Excel file loaded with columns: {raw_cols}")
    self.logger.info(f"Normalized headers: {norm_cols}")

    # Try to detect URL and comment columns
    url_col = self._detect_column(norm_cols, raw_cols, "url")
    comment_col = self._detect_column(norm_cols, raw_cols, "comment")

    # Special fallbacks for known inputs like: postUrl, Generated comment  (with trailing space)
    if url_col is None:
      for raw in raw_cols:
        if self._normalize(raw) in ("posturl", "tweet_url"):
          url_col = raw
          break
    if comment_col is None:
      for raw in raw_cols:
        norm = self._normalize(raw)
        if norm.startswith("generated_comment"):
          comment_col = raw
          break

    if url_col is None or comment_col is None:
      missing = []
      if url_col is None:
        missing.append("URL-like column (e.g., postUrl/url/link)")
      if comment_col is None:
        missing.append("comment-like column (e.g., Generated comment / comment)")
      raise ValueError(f"Could not detect required columns: {', '.join(missing)}")

    self.logger.info(f"Detected URL column: {url_col}")
    self.logger.info(f"Detected comment column: {comment_col}")

    # Create standard internal columns
    df["URL"] = df[url_col].astype(str).str.strip()
    df["generated_comment"] = df[comment_col].astype(str).str.replace(r"[\\r\\n]+", " ", regex=True).str.strip()

    # Optional: map author -> authorName if present
    author_like = None
    for raw in raw_cols:
      if self._normalize(raw) in ("author", "authorname"):
        author_like = raw
        break
    if author_like is not None:
      df["authorName"] = df[author_like]

    # Basic cleaning
    before = len(df)
    df = df.dropna(subset=["URL", "generated_comment"])
    df = df[(df["URL"] != "") & (df["generated_comment"] != "") & (df["URL"].str.lower() != "nan") & (df["generated_comment"].str.lower() != "nan")]
    self.logger.info(f"After cleaning empty rows: {before} -> {len(df)}")

    # Smart filtering with status column (create if missing)
    status_col = "Commented (Y/N)"
    if status_col not in self.original_df.columns:
      self.original_df[status_col] = ""
      self.logger.info("Created 'Commented (Y/N)' column (was missing).")
    if status_col not in df.columns:
      df[status_col] = ""

    # Skip Y rows
    if status_col in df.columns:
      already = (df[status_col] == "Y").sum()
      self.logger.info(f"Rows already commented (Y): {already}")
      df = df[df[status_col] != "Y"].copy()

    self.logger.info(f"Final count - {len(df)} rows will be processed")
    if len(df) > 0:
      self.logger.info("Sample data preview (rows to be processed):")
      for idx, row in df.head(3).iterrows():
        self.logger.info(f"  Row {idx}: URL={row['URL'][:80]}...")
        self.logger.info(f"  Row {idx}: Comment={row['generated_comment'][:80]}...")
        if "authorName" in row:
          self.logger.info(f"  Row {idx}: Author={row['authorName']}")
    else:
      self.logger.info("No uncommented posts found to process.")

    return df

  def update_excel_file(self, row_index: int, status: str):
    try:
      if self.original_df is not None:
        if "Commented (Y/N)" not in self.original_df.columns:
          self.original_df["Commented (Y/N)"] = ""
          self.logger.info("Created 'Commented (Y/N)' column in spreadsheet")
        self.original_df.loc[row_index, "Commented (Y/N)"] = status
        self.original_df.to_excel(self.sheet_path, index=False)
        self.logger.info(f"✓ Updated Excel file: Row {row_index} marked as '{status}'")
    except Exception as e:
      self.logger.error(f"Error updating Excel file: {str(e)}")

  def process_posts(self, df: pd.DataFrame):
    if len(df) == 0:
      self.logger.info("No posts to process - all rows already commented or no valid data found.")
      return
    self.logger.info(f"Starting to process {len(df)} uncommented posts...")
    for idx, row in df.iterrows():
      url = row["URL"]
      comment = row["generated_comment"]
      author_name = row.get("authorName", "Unknown")
      # Prefer 'PostText' if it exists in original, else 'content'
      content_preview = str(row.get("PostText", "") or row.get("content", ""))[:100] + "..." if (row.get("PostText") or row.get("content")) else "No content"

      if "Commented (Y/N)" in row and row["Commented (Y/N)"] == "Y":
        self.logger.info(f"⏭️  Skipping row {idx} - already commented")
        continue

      self.logger.info(f"Processing post {len(self.results) + 1}/{len(df)}")
      self.logger.info(f"  Row Index: {idx}")
      self.logger.info(f"  Author: {author_name}")
      self.logger.info(f"  Content: {content_preview}")
      self.logger.info(f"  URL: {url}")

      result = self.process_single_post(url, comment, len(self.results) + 1, idx)
      self.results.append(result)

      status = "Y" if result["status"] == "success" else "N"
      self.update_excel_file(idx, status)

      if len(self.results) < len(df):
        delay_time = self.delay + random.uniform(0.5, 1.5)
        self.logger.info(f"Waiting {delay_time:.1f} seconds before next post...")
        time.sleep(delay_time)

    self.logger.info("Finished processing all posts")

  def process_single_post(self, url: str, comment: str, post_number: int, original_index: int) -> Dict:
    result = {
      "post_number": post_number,
      "original_index": original_index,
      "url": url,
      "comment": comment[:50] + "..." if len(comment) > 50 else comment,
      "status": "failed",
      "message": "",
      "timestamp": datetime.now().isoformat()
    }
    max_retries = 3
    for attempt in range(max_retries):
      try:
        self.driver.execute_script("window.open('');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.driver.get(url)
        time.sleep(3)
        if self.post_comment(comment):
          result["status"] = "success"
          result["message"] = "Comment posted successfully"
          self.logger.info(f"✓ Post {post_number}: Comment posted successfully")
          break
        else:
          result["message"] = f"Failed to post comment (attempt {attempt + 1})"
      except Exception as e:
        error_msg = f"Error on attempt {attempt + 1}: {str(e)}"
        result["message"] = error_msg
        self.logger.error(f"✗ Post {post_number}: {error_msg}")
        if attempt < max_retries - 1:
          wait_time = 2 ** attempt
          self.logger.info(f"Retrying in {wait_time} seconds...")
          time.sleep(wait_time)
      finally:
        try:
          self.driver.close()
          self.driver.switch_to.window(self.main_window)
        except Exception:
          pass
    return result

  def post_comment(self, comment: str) -> bool:
    try:
      comment = comment.replace("\n", " ").replace("\r", " ").strip()
      self.logger.info(f"Attempting to post comment: {comment[:50]}...")

      # 1) Open reply box
      reply_button_selectors = [
        "[data-testid='reply']",
        "[aria-label*='Reply']",
        "[data-testid='tweetButtonInline']"
      ]
      reply_button = None
      for selector in reply_button_selectors:
        try:
          reply_button = WebDriverWait(self.driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
          )
          self.logger.info(f"Found reply button with selector: {selector}")
          break
        except TimeoutException:
          self.logger.info(f"Reply button selector {selector} not found, trying next...")
          continue
      if not reply_button:
        self.logger.error("Could not find reply button")
        return False

      self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", reply_button)
      time.sleep(1)
      self.logger.info("Clicking reply button...")
      reply_button.click()
      time.sleep(2)

      # 2) Find compose area
      compose_selectors = [
        "[data-testid='tweetTextarea_0']",
        "[contenteditable='true'][role='textbox']",
        ".public-DraftEditor-content",
        "[aria-label*='Post your reply']",
        "[placeholder*='Post your reply']"
      ]
      compose_area = None
      for selector in compose_selectors:
        try:
          compose_area = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
          )
          self.logger.info(f"Found compose area with selector: {selector}")
          break
        except TimeoutException:
          continue
      if not compose_area:
        self.logger.error("Could not find compose text area")
        return False

      self.logger.info("Clicking on compose area...")
      compose_area.click()
      time.sleep(1)

      # 3) Enter text
      self.logger.info("Inputting comment text...")
      try:
        compose_area.clear()
        compose_area.send_keys(comment)
        self.logger.info("Comment text entered successfully using send_keys")
      except Exception as e:
        self.logger.warning(f"send_keys method failed: {e}, trying ActionChains method")
        try:
          actions = ActionChains(self.driver)
          actions.click(compose_area)
          actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)
          actions.send_keys(comment)
          actions.perform()
          self.logger.info("Comment text entered using ActionChains")
        except Exception as e2:
          self.logger.warning(f"ActionChains method failed: {e2}, trying JavaScript method")
          self.driver.execute_script(
            "arguments[0].innerText = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
            compose_area,
            comment
          )
          self.logger.info("Comment text entered using JavaScript")

      # 4) Click Post/Reply
      self.logger.info("Waiting for Post/Reply button to become enabled...")
      time.sleep(2)
      post_button_selectors = [
        "[data-testid='tweetButton']",
        "[data-testid='tweetButtonInline']",
        "button[role='button']",
        "[aria-label*='Reply']",
        "[aria-label*='Post']"
      ]
      post_button = None
      for selector in post_button_selectors:
        try:
          if selector == "button[role='button']":
            xpath_selector = "//button[not(@disabled) and (contains(., 'Reply') or contains(., 'Post'))]"
            post_button = WebDriverWait(self.driver, 8).until(
              EC.element_to_be_clickable((By.XPATH, xpath_selector))
            )
          else:
            post_button = WebDriverWait(self.driver, 8).until(
              EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
          if post_button.is_enabled():
            self.logger.info(f"Found enabled post button with selector: {selector}")
            break
          else:
            self.logger.info(f"Post button found but disabled: {selector}")
            post_button = None
        except TimeoutException:
          self.logger.info(f"Post button selector '{selector}' not found, trying next...")
          continue
      if not post_button:
        self.logger.error("Could not find enabled Post/Reply button")
        return False

      self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_button)
      time.sleep(1)
      self.logger.info("Clicking Post/Reply button...")
      post_button.click()

      # 5) Verify
      self.logger.info("Waiting for comment to be posted...")
      time.sleep(5)
      try:
        success_indicators = ["[data-testid='tweet']", "[data-testid='cellInnerDiv']"]
        for indicator in success_indicators:
          try:
            WebDriverWait(self.driver, 3).until(
              EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
            )
            self.logger.info(f"Comment posting verified via: {indicator}")
            break
          except TimeoutException:
            continue
      except Exception as e:
        self.logger.warning(f"Could not verify comment posting: {e}")

      self.logger.info("Comment posting process completed successfully")
      return True

    except Exception as e:
      self.logger.error(f"Error posting comment: {str(e)}")
      return False

  def generate_summary_report(self) -> str:
    total_posts = len(self.results)
    successful_posts = len([r for r in self.results if r["status"] == "success"])
    failed_posts = total_posts - successful_posts
    success_rate = (successful_posts / total_posts * 100) if total_posts > 0 else 0
    summary = f"""
X (Twitter) Commenter Bot - Session Summary
===========================================
Total posts processed: {total_posts}
Comments posted successfully: {successful_posts}
Failed attempts: {failed_posts}
Success rate: {success_rate:.1f}%

Excel file updated: {self.sheet_path}
Session completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Note: Posts already marked as 'Y' were automatically skipped.
"""
    if failed_posts > 0:
      summary += "\nFailed Posts:\n"
      for result in self.results:
        if result["status"] == "failed":
          summary += f"- Post {result['post_number']} (Row {result['original_index']}): {result['message']}\n"
    return summary

  def save_results(self) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"x_results_{timestamp}.csv"
    df_results = pd.DataFrame(self.results)
    df_results.to_csv(results_file, index=False)
    self.logger.info(f"Results saved to: {results_file}")
    return results_file

  def cleanup(self):
    if self.driver:
      try:
        self.driver.quit()
        self.logger.info("Browser closed successfully")
      except Exception as e:
        self.logger.error(f"Error closing browser: {str(e)}")

  def run(self, sheet_path: str) -> int:
    try:
      self.setup_chrome_driver()
      self.navigate_to_login()
      if not self.wait_for_manual_login():
        self.logger.error("Login confirmation failed. Exiting...")
        return 2

      df = self.load_spreadsheet(sheet_path)
      if len(df) == 0:
        self.logger.info("No uncommented posts found to process.")
        return 0

      self.process_posts(df)

      summary = self.generate_summary_report()
      print(summary)
      self.logger.info(summary)

      if len(self.results) > 0:
        _ = self.save_results()

      failed_count = len([r for r in self.results if r["status"] == "failed"])
      if failed_count == 0:
        return 0
      elif failed_count < len(self.results):
        return 1
      else:
        return 1

    except Exception as e:
      self.logger.error(f"Fatal error: {str(e)}")
      return 1
    finally:
      self.cleanup()


def main():
  parser = argparse.ArgumentParser(
    description="X (Twitter) Commenter Bot - Adaptive Columns + In-Browser Login Confirm",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="""
Examples:
  python x_commenter_bot.py --sheet 5postsX.xlsx
  python x_commenter_bot.py --sheet 5postsX.xlsx --delay 2.5

Features:
- Detects URL and comment columns automatically (e.g., postUrl, Generated comment )
- Skips rows already marked as 'Y' in the "Commented (Y/N)" column
- Updates the spreadsheet with 'Y' for successful comments and 'N' for failures
- Creates the "Commented (Y/N)" column if it doesn't exist
- UI overlay to confirm login (no terminal interaction)
"""
  )
  parser.add_argument("--sheet", required=True, help="Path to Excel file (.xlsx) with X post data")
  parser.add_argument("--delay", type=float, default=2.0, help="Seconds to sleep between actions (default: 2.0)")
  parser.add_argument("--profile", help="Path to Chrome profile directory (optional)")
  args = parser.parse_args()

  if not args.sheet.lower().endswith(".xlsx"):
    print("Error: This script works with Excel files (.xlsx)")
    sys.exit(1)

  bot = XCommentBot(delay=args.delay, profile_path=args.profile)
  exit_code = bot.run(args.sheet)
  sys.exit(exit_code)


if __name__ == "__main__":
  main()
