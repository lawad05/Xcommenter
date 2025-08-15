#!/usr/bin/env python3
"""
X (Twitter) Commenter Bot - Fixed and Optimized Version

This script automates X (Twitter) commenting using Selenium with a hybrid interactive login.
Fixes and optimizations:
- Fixed OSError(22) by improving path resolution and file handling
- Better handling of column names with trailing spaces
- Improved error handling and fallback mechanisms
- Optimized Excel reading with proper encoding detection
- Enhanced status column detection and creation
- Better synchronization with Streamlit UI
- Improved logging and progress reporting

Author: AI Assistant (Fixed Version)
Version: 2.0
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
from io import BytesIO
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple, Callable

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
    Automates X (Twitter) commenting with adaptive spreadsheet parsing and a no-terminal login flow.
    """

    def __init__(self, delay: float = 2.0, profile_path: str | None = None, headless: bool = False):
        self.delay = delay
        self.profile_path = profile_path
        self.headless = headless
        self.driver = None
        self.wait = None
        self.main_window = None
        self.results: List[Dict] = []
        self.original_df: Optional[pd.DataFrame] = None
        self.sheet_path: Optional[str] = None
        self._status_col_name: Optional[str] = None
        self._source_desc: str = ""
        self.ui_callback: Optional[Callable] = None
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

    def log_and_callback(self, message: str, level: str = "info"):
        """Log message and call UI callback if available"""
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        
        if self.ui_callback:
            try:
                self.ui_callback(message)
            except Exception:
                pass  # Don't let UI callback errors break the main flow

    def setup_chrome_driver(self) -> webdriver.Chrome:
        self.log_and_callback("Setting up Chrome WebDriver...")
        driver_path = chromedriver_autoinstaller.install()
        self.log_and_callback(f"ChromeDriver installed at: {driver_path}")
        
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--window-size=1280,900")
        else:
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
            self.log_and_callback(f"Using temporary profile directory: {temp_dir}")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        service = Service(driver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 20)
        self.log_and_callback("Chrome WebDriver setup completed successfully")
        return self.driver

    def navigate_to_login(self):
        self.log_and_callback("Navigating to X login page...")
        self.driver.get("https://x.com/i/flow/login")
        self.main_window = self.driver.current_window_handle
        self.log_and_callback("X login page loaded")

    def wait_for_manual_login(self):
        return self.wait_for_manual_login_ui()

    def wait_for_manual_login_ui(self) -> bool:
        """
        Floating panel with an "I'm logged in" button.
        Keeps the panel visible across redirects by re-injecting it if it disappears.
        """
        try:
            self.log_and_callback("=" * 60)
            self.log_and_callback("LOGIN FLOW")
            self.log_and_callback("1) Log in on X in the opened Chrome window.")
            self.log_and_callback("2) Click the floating 'I'm logged in' button to continue.")
            self.log_and_callback("=" * 60)

            self._inject_overlay_panel()

            start = time.time()
            timeout_seconds = 15 * 60
            last_log = 0
            last_url = ""

            while True:
                try:
                    present = self.driver.execute_script("return !!document.getElementById('xbot-login-overlay');")
                except Exception:
                    present = True

                try:
                    current_url = self.driver.current_url
                except Exception:
                    current_url = last_url

                if (not present) or (current_url != last_url):
                    try:
                        self._inject_overlay_panel()
                    except Exception:
                        pass
                    last_url = current_url

                try:
                    flag = self.driver.execute_script("return window.localStorage.getItem('xbot_login_ok');")
                except Exception:
                    flag = None

                if flag == "1":
                    self.log_and_callback("Login confirmed via UI button.")
                    try:
                        self.driver.execute_script("window.localStorage.removeItem('xbot_login_ok');")
                    except Exception:
                        pass
                    try:
                        self.driver.execute_script("var el = document.getElementById('xbot-login-overlay'); if (el) { el.remove(); }")
                    except Exception:
                        pass
                    break

                if self.confirm_login():
                    self.log_and_callback("Login auto-confirmed via page indicators.")
                    try:
                        self.driver.execute_script("var el = document.getElementById('xbot-login-overlay'); if (el) { el.remove(); }")
                    except Exception:
                        pass
                    break

                if time.time() - start > timeout_seconds:
                    self.log_and_callback("Login wait timed out after 15 minutes.", "error")
                    raise TimeoutException("Login not confirmed within timeout.")

                if time.time() - last_log > 10:
                    self.log_and_callback("Waiting for login confirmation... (click the overlay button when ready)")
                    last_log = time.time()

                time.sleep(1.0)

            return True

        except Exception as e:
            self.log_and_callback(f"Error during UI login wait: {str(e)}", "error")
            return False

    def _inject_overlay_panel(self):
        try:
            self.driver.execute_script(
                """
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

                  btn.addEventListener('click', function(){
                    try { window.localStorage.setItem('xbot_login_ok', '1'); } catch(e){}
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
                """
            )
            self.log_and_callback("Injected login confirmation overlay into the page.")
        except Exception as e:
            self.log_and_callback(f"Could not inject overlay panel: {e}", "warning")

    def confirm_login(self) -> bool:
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
                    if element is not None:
                        self.log_and_callback(f"Login confirmed via element: {selector}")
                        return True
                except TimeoutException:
                    continue
            
            current_url = self.driver.current_url
            if ("/home" in current_url) or (("x.com" in current_url) and ("/login" not in current_url)):
                self.log_and_callback(f"Login confirmed via URL pattern: {current_url}")
                return True
            return False
        except Exception as e:
            self.log_and_callback(f"Error during login confirmation: {str(e)}", "error")
            return False

    @staticmethod
    def _normalize(col: str) -> str:
        """Normalize column names for comparison"""
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
        """Detect column by type with improved matching"""
        candidates = []
        for norm, raw in zip(norm_cols, raw_cols):
            if want == "url":
                if norm in ("url", "posturl", "tweet_url", "link", "post_link"):
                    candidates.append(raw)
                elif ("url" in norm) and (("post" in norm) or ("tweet" in norm) or (norm == "url")):
                    candidates.append(raw)
            elif want == "comment":
                if norm in ("generated_comment", "comment", "reply", "comment_text", "generatedcomment"):
                    candidates.append(raw)
                elif ("comment" in norm) or ("reply" in norm) or ("generated" in norm and "comment" in norm):
                    candidates.append(raw)
        
        if len(candidates) > 0:
            return candidates[0]
        return None

    def _resolve_sheet_path(self, sheet_path: str) -> Path:
        """Improved path resolution with better error handling"""
        sp = str(sheet_path).strip().strip('"').strip("'")
        
        # Remove problematic prefixes
        for bad_prefix in ("file://", "sandbox:"):
            if sp.startswith(bad_prefix):
                sp = sp[len(bad_prefix):]
        
        p = Path(sp).expanduser().resolve()
        
        # If path is not absolute, make it relative to current working directory
        if not p.is_absolute():
            p = Path.cwd().resolve() / p
        
        # Check if file exists
        if p.exists():
            return p
        
        # Try to find file in script directory
        try:
            script_dir = Path(__file__).parent.resolve()
            alt = script_dir / p.name
            if alt.exists():
                return alt
        except Exception:
            pass
        
        # Try case-insensitive search in current directory
        try:
            cwd = Path.cwd().resolve()
            for candidate in cwd.glob("*"):
                if candidate.name.lower() == p.name.lower():
                    return candidate
        except Exception:
            pass
        
        return p

    def load_spreadsheet(self, sheet_input: Any) -> pd.DataFrame:
        """Robust spreadsheet loader with improved error handling"""
        self.log_and_callback(f"Loading spreadsheet from: {type(sheet_input).__name__}")

        df = None
        read_errors: List[str] = []

        # Case 1: Streamlit UploadedFile or file-like object
        if hasattr(sheet_input, "read") and callable(sheet_input.read):
            try:
                # Reset file pointer if possible
                if hasattr(sheet_input, "seek"):
                    sheet_input.seek(0)
                
                raw = sheet_input.read()
                name = getattr(sheet_input, "name", "input.xlsx")
                ext = Path(name).suffix.lower() or ".xlsx"
                bio = BytesIO(raw)
                self._source_desc = f"uploaded-file:{name}"
                
                # Set a writable output path
                out_name = f"processed_{Path(name).stem}{ext}"
                self.sheet_path = str((Path.cwd() / out_name).resolve())
                
                if ext == ".csv":
                    # Try different encodings for CSV
                    for encoding in ["utf-8", "latin1", "cp1252"]:
                        try:
                            bio.seek(0)
                            df = pd.read_csv(bio, encoding=encoding)
                            self.log_and_callback(f"Successfully read CSV with {encoding} encoding")
                            break
                        except Exception as e:
                            read_errors.append(f"CSV {encoding}: {repr(e)}")
                else:
                    # Try different engines for Excel
                    for engine in ["openpyxl", None, "calamine"]:
                        try:
                            bio.seek(0)
                            if engine == "calamine":
                                try:
                                    df = pd.read_excel(bio, engine="calamine")
                                except ImportError:
                                    continue  # Skip if calamine not available
                            else:
                                df = pd.read_excel(bio, engine=engine)
                            self.log_and_callback(f"Successfully read Excel with {engine or 'auto'} engine")
                            break
                        except Exception as e:
                            read_errors.append(f"Excel {engine or 'auto'}: {repr(e)}")
                            
            except Exception as e:
                read_errors.append(f"File-like object processing: {repr(e)}")

        # Case 2: Raw bytes
        elif isinstance(sheet_input, (bytes, bytearray)):
            try:
                bio = BytesIO(sheet_input)
                self._source_desc = "bytes"
                self.sheet_path = str((Path.cwd() / f"processed_{int(time.time())}.xlsx").resolve())
                
                for engine in ["openpyxl", None, "calamine"]:
                    try:
                        bio.seek(0)
                        if engine == "calamine":
                            try:
                                df = pd.read_excel(bio, engine="calamine")
                            except ImportError:
                                continue
                        else:
                            df = pd.read_excel(bio, engine=engine)
                        self.log_and_callback(f"Successfully read bytes with {engine or 'auto'} engine")
                        break
                    except Exception as e:
                        read_errors.append(f"Bytes {engine or 'auto'}: {repr(e)}")
                        
            except Exception as e:
                read_errors.append(f"Bytes processing: {repr(e)}")

        # Case 3: String/Path-like (IMPROVED)
        else:
            path_str = str(sheet_input)
            resolved = self._resolve_sheet_path(path_str)
            self.sheet_path = str(resolved)
            self._source_desc = f"path:{self.sheet_path}"
            self.log_and_callback(f"Resolved sheet path: {self.sheet_path}")
            
            if not resolved.exists():
                cwd = Path.cwd()
                self.log_and_callback(f"Input file not found. CWD: {cwd}", "error")
                raise FileNotFoundError(f"Input file not found at: {resolved}")

            ext = resolved.suffix.lower()

            if ext == ".csv":
                # Try different encodings for CSV files
                for encoding in ["utf-8", "latin1", "cp1252"]:
                    try:
                        df = pd.read_csv(self.sheet_path, encoding=encoding)
                        self.log_and_callback(f"Successfully read CSV with {encoding} encoding")
                        break
                    except Exception as e:
                        read_errors.append(f"CSV {encoding}: {repr(e)}")
            else:
                # IMPROVED Excel reading with multiple fallback strategies
                strategies = [
                    # Strategy 1: Direct pandas read_excel
                    lambda: pd.read_excel(self.sheet_path, engine="openpyxl"),
                    # Strategy 2: Open in binary mode first
                    lambda: pd.read_excel(open(self.sheet_path, "rb"), engine="openpyxl"),
                    # Strategy 3: Try auto engine
                    lambda: pd.read_excel(self.sheet_path, engine=None),
                    # Strategy 4: Binary mode with auto engine
                    lambda: pd.read_excel(open(self.sheet_path, "rb"), engine=None),
                    # Strategy 5: Try calamine if available
                    lambda: pd.read_excel(self.sheet_path, engine="calamine"),
                    # Strategy 6: Binary mode with calamine
                    lambda: pd.read_excel(open(self.sheet_path, "rb"), engine="calamine"),
                ]
                
                for i, strategy in enumerate(strategies, 1):
                    try:
                        df = strategy()
                        self.log_and_callback(f"Successfully read Excel with strategy {i}")
                        break
                    except ImportError:
                        if "calamine" in str(strategy):
                            continue  # Skip calamine if not available
                    except Exception as e:
                        read_errors.append(f"Strategy {i}: {repr(e)}")

        if df is None:
            error_msg = "Error reading input file after fallbacks: " + " | ".join(read_errors)
            self.log_and_callback(error_msg, "error")
            raise ValueError(error_msg)

        # Keep a copy for writing status back
        self.original_df = df.copy()

        # Clean up column names and drop empty unnamed columns
        df.columns = [str(col).strip() for col in df.columns]  # Remove trailing spaces
        df = df.loc[:, [c for c in df.columns if not (str(c).startswith("Unnamed") and pd.isna(df[c]).all())]]

        raw_cols = list(df.columns)
        norm_cols = [self._normalize(c) for c in raw_cols]
        self.log_and_callback(f"Loaded columns: {raw_cols}")
        self.log_and_callback(f"Normalized headers: {norm_cols}")

        # Detect URL and comment columns
        url_col = self._detect_column(norm_cols, raw_cols, "url")
        comment_col = self._detect_column(norm_cols, raw_cols, "comment")

        # Fallback detection for URL column
        if url_col is None:
            for raw in raw_cols:
                if self._normalize(raw) in ("posturl", "tweet_url", "url", "link"):
                    url_col = raw
                    break
        
        # Fallback detection for comment column
        if comment_col is None:
            for raw in raw_cols:
                norm = self._normalize(raw)
                if norm.startswith("generated_comment") or ("comment" in norm) or ("reply" in norm):
                    comment_col = raw
                    break

        if (url_col is None) or (comment_col is None):
            missing = []
            if url_col is None:
                missing.append("URL-like column (e.g., postUrl/url/link)")
            if comment_col is None:
                missing.append("comment-like column (e.g., Generated comment / comment / reply)")
            error_msg = f"Could not detect required columns: {', '.join(missing)}"
            self.log_and_callback(error_msg, "error")
            raise ValueError(error_msg)

        self.log_and_callback(f"Detected URL column: {url_col}")
        self.log_and_callback(f"Detected comment column: {comment_col}")

        # Standardize column names
        df["URL"] = df[url_col].astype(str).str.strip()
        df["generated_comment"] = (
            df[comment_col]
            .astype(str)
            .str.replace("\n", " ")
            .str.replace("\r", " ")
            .str.strip()
        )

        # Optional author column
        author_like = None
        for raw in raw_cols:
            if self._normalize(raw) in ("author", "authorname", "user", "username"):
                author_like = raw
                break
        if author_like is not None:
            df["authorName"] = df[author_like]

        # Detect or create status column
        status_candidates = {"commented_(y/n)", "commented", "done", "posted", "status"}
        status_col = None
        for norm, raw in zip(norm_cols, raw_cols):
            if norm in status_candidates:
                status_col = raw
                break
        
        if status_col is None:
            status_col = "Commented (Y/N)"
            if status_col not in self.original_df.columns:
                self.original_df[status_col] = ""
                self.log_and_callback("Created 'Commented (Y/N)' column (was missing).")

        # Clean and filter data
        before = len(df)
        df = df.dropna(subset=["URL", "generated_comment"])
        df = df[
            (df["URL"].astype(str).str.len() > 0) &
            (df["generated_comment"].astype(str).str.len() > 0) &
            (df["URL"].str.lower() != "nan") &
            (df["generated_comment"].str.lower() != "nan")
        ]
        self.log_and_callback(f"After cleaning empty rows: {before} -> {len(df)}")

        # Filter out already commented rows
        if status_col in df.columns:
            already = (df[status_col].astype(str).str.upper().str.strip().isin(["Y", "YES", "TRUE", "1"]))
            self.log_and_callback(f"Rows already commented (Y/YES/TRUE/1): {already.sum()}")
            df = df[~already].copy()

        self._status_col_name = status_col

        self.log_and_callback(f"Final count - {len(df)} rows will be processed")
        if len(df) > 0:
            self.log_and_callback("Sample data preview (rows to be processed):")
            for idx, row in df.head(3).iterrows():
                self.log_and_callback(f"  Row {idx}: URL={str(row['URL'])[:80]}...")
                self.log_and_callback(f"  Row {idx}: Comment={str(row['generated_comment'])[:80]}...")
                if "authorName" in df.columns:
                    self.log_and_callback(f"  Row {idx}: Author={row['authorName']}")
        else:
            self.log_and_callback("No uncommented posts found to process.")

        return df

    def update_excel_file(self, row_index: int, status: str):
        """Update Excel file with improved error handling"""
        try:
            if self.original_df is None:
                return
            
            status_col = self._status_col_name if self._status_col_name else "Commented (Y/N)"
            if status_col not in self.original_df.columns:
                self.original_df[status_col] = ""
                self.log_and_callback("Created status column in spreadsheet")

            self.original_df.loc[row_index, status_col] = status

            out_path = self.sheet_path or str((Path.cwd() / f"processed_{int(time.time())}.xlsx").resolve())
            ext = Path(out_path).suffix.lower()
            
            try:
                if ext == ".csv":
                    self.original_df.to_csv(out_path, index=False, encoding="utf-8")
                else:
                    # Use openpyxl engine explicitly for better compatibility
                    self.original_df.to_excel(out_path, index=False, engine="openpyxl")
                self.log_and_callback(f"✓ Updated file: Row {row_index} marked as '{status}' → {out_path}")
            except (OSError, PermissionError) as e:
                # If writing back to original target fails, write to a new file
                alt = str((Path.cwd() / f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx").resolve())
                self.original_df.to_excel(alt, index=False, engine="openpyxl")
                self.sheet_path = alt
                self.log_and_callback(f"Write failed to {out_path} ({e}). Wrote to {alt} instead.", "warning")
        except Exception as e:
            self.log_and_callback(f"Error updating file: {str(e)}", "error")

    def process_posts(self, df: pd.DataFrame):
        """Process posts with improved progress reporting"""
        if len(df) == 0:
            self.log_and_callback("No posts to process - all rows already commented or no valid data found.")
            return
        
        self.log_and_callback(f"Starting to process {len(df)} uncommented posts...")
        
        for idx, row in df.iterrows():
            url = row["URL"]
            comment = row["generated_comment"]
            author_name = row.get("authorName", "Unknown")
            content_preview = str(row.get("PostText", "") or row.get("content", ""))[:100] + "..." if (row.get("PostText") or row.get("content")) else "No content"

            if (self._status_col_name in row) and (str(row[self._status_col_name]).strip().upper() in {"Y", "YES", "TRUE", "1"}):
                self.log_and_callback(f"⏭️  Skipping row {idx} - already commented")
                continue

            current_post = len(self.results) + 1
            self.log_and_callback(f"Processing post {current_post}/{len(df)}")
            self.log_and_callback(f"  Row Index: {idx}")
            self.log_and_callback(f"  Author: {author_name}")
            self.log_and_callback(f"  Content: {content_preview}")
            self.log_and_callback(f"  URL: {url}")

            result = self.process_single_post(url, comment, current_post, idx)
            self.results.append(result)

            status = "Y" if result["status"] == "success" else "N"
            self.update_excel_file(idx, status)

            # Progress update for UI
            if self.ui_callback:
                progress = f"Completed {current_post}/{len(df)} posts"
                self.ui_callback(progress)

            if current_post < len(df):
                delay_time = self.delay + random.uniform(0.5, 1.5)
                self.log_and_callback(f"Waiting {delay_time:.1f} seconds before next post...")
                time.sleep(delay_time)

        self.log_and_callback("Finished processing all posts")

    def process_single_post(self, url: str, comment: str, post_number: int, original_index: int) -> Dict:
        """Process a single post with improved error handling"""
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
                    self.log_and_callback(f"✓ Post {post_number}: Comment posted successfully")
                    break
                else:
                    result["message"] = f"Failed to post comment (attempt {attempt + 1})"
                    
            except Exception as e:
                error_msg = f"Error on attempt {attempt + 1}: {str(e)}"
                result["message"] = error_msg
                self.log_and_callback(f"✗ Post {post_number}: {error_msg}", "error")
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    self.log_and_callback(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            finally:
                try:
                    self.driver.close()
                    self.driver.switch_to.window(self.main_window)
                except Exception:
                    pass
                    
        return result

    def post_comment(self, comment: str) -> bool:
        """Post comment with improved element detection"""
        try:
            comment = comment.replace("\n", " ").replace("\r", " ").strip()
            self.log_and_callback(f"Attempting to post comment: {comment[:50]}...")

            # Find reply button with improved selectors
            reply_button_selectors = [
                "[data-testid='reply']",
                "[aria-label*='Reply']",
                "[data-testid='tweetButtonInline']",
                "button[aria-label*='Reply']"
            ]
            
            reply_button = None
            for selector in reply_button_selectors:
                try:
                    reply_button = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self.log_and_callback(f"Found reply button with selector: {selector}")
                    break
                except TimeoutException:
                    self.log_and_callback(f"Reply button selector {selector} not found, trying next...")
                    continue
                    
            if reply_button is None:
                self.log_and_callback("Could not find reply button", "error")
                return False

            # Scroll to and click reply button
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", reply_button)
            time.sleep(1)
            self.log_and_callback("Clicking reply button...")
            reply_button.click()
            time.sleep(2)

            # Find compose area with improved selectors
            compose_selectors = [
                "[data-testid='tweetTextarea_0']",
                "[contenteditable='true'][role='textbox']",
                ".public-DraftEditor-content",
                "[aria-label*='Post your reply']",
                "[placeholder*='Post your reply']",
                "div[contenteditable='true']"
            ]
            
            compose_area = None
            for selector in compose_selectors:
                try:
                    compose_area = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self.log_and_callback(f"Found compose area with selector: {selector}")
                    break
                except TimeoutException:
                    continue
                    
            if compose_area is None:
                self.log_and_callback("Could not find compose text area", "error")
                return False

            # Input comment text with multiple fallback methods
            self.log_and_callback("Clicking on compose area...")
            compose_area.click()
            time.sleep(1)

            self.log_and_callback("Inputting comment text...")
            input_success = False
            
            # Method 1: Standard send_keys
            try:
                compose_area.clear()
                compose_area.send_keys(comment)
                input_success = True
                self.log_and_callback("Comment text entered successfully using send_keys")
            except Exception as e:
                self.log_and_callback(f"send_keys method failed: {e}", "warning")
                
                # Method 2: ActionChains
                try:
                    actions = ActionChains(self.driver)
                    actions.click(compose_area)
                    actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL)
                    actions.send_keys(comment)
                    actions.perform()
                    input_success = True
                    self.log_and_callback("Comment text entered using ActionChains")
                except Exception as e2:
                    self.log_and_callback(f"ActionChains method failed: {e2}", "warning")
                    
                    # Method 3: JavaScript
                    try:
                        self.driver.execute_script(
                            "arguments[0].innerText = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                            compose_area,
                            comment
                        )
                        input_success = True
                        self.log_and_callback("Comment text entered using JavaScript")
                    except Exception as e3:
                        self.log_and_callback(f"JavaScript method failed: {e3}", "error")

            if not input_success:
                self.log_and_callback("Failed to input comment text with all methods", "error")
                return False

            # Find and click post button
            self.log_and_callback("Waiting for Post/Reply button to become enabled...")
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
                        self.log_and_callback(f"Found enabled post button with selector: {selector}")
                        break
                    else:
                        self.log_and_callback(f"Post button found but disabled: {selector}")
                        post_button = None
                except TimeoutException:
                    self.log_and_callback(f"Post button selector '{selector}' not found, trying next...")
                    continue
                    
            if post_button is None:
                self.log_and_callback("Could not find enabled Post/Reply button", "error")
                return False

            # Click post button
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post_button)
            time.sleep(1)
            self.log_and_callback("Clicking Post/Reply button...")
            post_button.click()

            # Wait and verify posting
            self.log_and_callback("Waiting for comment to be posted...")
            time.sleep(5)
            
            try:
                success_indicators = ["[data-testid='tweet']", "[data-testid='cellInnerDiv']"]
                for indicator in success_indicators:
                    try:
                        WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                        )
                        self.log_and_callback(f"Comment posting verified via: {indicator}")
                        break
                    except TimeoutException:
                        continue
            except Exception as e:
                self.log_and_callback(f"Could not verify comment posting: {e}", "warning")

            self.log_and_callback("Comment posting process completed successfully")
            return True

        except Exception as e:
            self.log_and_callback(f"Error posting comment: {str(e)}", "error")
            return False

    def generate_summary_report(self) -> str:
        """Generate summary report"""
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

Excel/CSV updated: {self.sheet_path}
Source: {self._source_desc}
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
        """Save results to CSV"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"x_results_{timestamp}.csv"
        df_results = pd.DataFrame(self.results)
        df_results.to_csv(results_file, index=False)
        self.log_and_callback(f"Results saved to: {results_file}")
        return results_file

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
                self.log_and_callback("Browser closed successfully")
            except Exception as e:
                self.log_and_callback(f"Error closing browser: {str(e)}", "error")

    def run(self, sheet_path: Any, ui_mode: bool = False, on_update: Optional[Callable] = None) -> int:
        """Main run method with improved UI integration"""
        try:
            # Set UI callback if provided
            if on_update:
                self.ui_callback = on_update
            
            self.setup_chrome_driver()
            self.navigate_to_login()
            
            if not self.wait_for_manual_login():
                self.log_and_callback("Login confirmation failed. Exiting...", "error")
                return 2

            df = self.load_spreadsheet(sheet_path)
            if len(df) == 0:
                self.log_and_callback("No uncommented posts found to process.")
                return 4

            self.process_posts(df)

            summary = self.generate_summary_report()
            print(summary)
            self.log_and_callback(summary)

            if len(self.results) > 0:
                _ = self.save_results()

            successful = len([r for r in self.results if r["status"] == "success"]) > 0
            if successful:
                return 0
            else:
                return 3

        except FileNotFoundError as e:
            self.log_and_callback(f"File not found: {e}", "error")
            return 1
        except Exception as e:
            self.log_and_callback(f"Fatal error: {str(e)}", "error")
            return 1
        finally:
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(
        description="X (Twitter) Commenter Bot - Fixed and Optimized Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python x_commenter_bot_fixed.py --sheet posts.xlsx
  python x_commenter_bot_fixed.py --sheet posts.csv --delay 2.5

Features:
- Fixed OSError(22) with improved path resolution and file handling
- Better handling of column names with trailing spaces
- Improved error handling and fallback mechanisms
- Enhanced status column detection and creation
- Better synchronization with Streamlit UI
- Optimized Excel reading with proper encoding detection
"""
    )
    parser.add_argument("--sheet", required=True, help="Path to .xlsx or .csv with X post data")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds to sleep between actions (default: 2.0)")
    parser.add_argument("--profile", help="Path to Chrome profile directory (optional)")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    args = parser.parse_args()

    if not (args.sheet.lower().endswith(".xlsx") or args.sheet.lower().endswith(".csv")):
        print("Error: This script works with .xlsx or .csv files")
        sys.exit(1)

    bot = XCommentBot(delay=args.delay, profile_path=args.profile, headless=args.headless)
    exit_code = bot.run(args.sheet)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

