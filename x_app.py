import sys, os, importlib, inspect
import streamlit as st
from pathlib import Path
import pandas as pd
import time

# Prefer local dir for imports
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="X Auto Commenter", page_icon="🧵", layout="centered")
st.title("🧵 X (Twitter) Auto Commenter – Enhanced UI")

# Initialize session state
if "logs" not in st.session_state:
    st.session_state["logs"] = []
if "processing" not in st.session_state:
    st.session_state["processing"] = False

# UI Components
uploaded_file = st.file_uploader("1️⃣ Upload your Excel/CSV", type=["xlsx", "csv"])
delay = st.slider("2️⃣ Delay between comments (seconds)", 0.5, 5.0, 1.5, 0.1)
profile = st.text_input("3️⃣ (Optional) Chrome profile folder")
headless = st.checkbox("Run headless (no visible browser)", value=False)

# Progress tracking
progress_container = st.container()
log_container = st.container()

def ui_log(msg: str) -> None:
    """Enhanced logging with timestamp and better formatting"""
    timestamp = time.strftime("%H:%M:%S")
    formatted_msg = f"[{timestamp}] {str(msg)}"
    
    prev = st.session_state.get("logs", [])
    prev.append(formatted_msg)
    st.session_state["logs"] = prev[-200:]  # Keep last 200 logs
    
    # Update log display
    with log_container:
        st.text_area("📋 Live Logs", 
                    value="\n".join(st.session_state["logs"]), 
                    height=300, 
                    key=f"logs_{len(st.session_state['logs'])}")

def preview_columns(file):
    """Enhanced file preview with better error handling"""
    try:
        if file.name.lower().endswith(".csv"):
            # Try different encodings for CSV
            for encoding in ["utf-8", "latin1", "cp1252"]:
                try:
                    df = pd.read_csv(file, encoding=encoding)
                    st.success(f"✅ CSV file loaded successfully with {encoding} encoding")
                    break
                except Exception:
                    continue
            else:
                st.error("❌ Could not read CSV file with any encoding")
                return
        else:
            # Try different engines for Excel
            for engine in ["openpyxl", None]:
                try:
                    df = pd.read_excel(file, engine=engine, sheet_name=0)
                    st.success(f"✅ Excel file loaded successfully with {engine or 'auto'} engine")
                    break
                except Exception as e:
                    if engine is None:  # Last attempt
                        st.error(f"❌ Could not read Excel file: {e}")
                        return
                    continue
        
        # Display file info
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"📊 **Rows:** {len(df)}")
        with col2:
            st.info(f"📋 **Columns:** {len(df.columns)}")
        
        # Show columns with better formatting
        st.write("**Detected columns:**")
        for i, col in enumerate(df.columns, 1):
            col_clean = str(col).strip()
            if col_clean.startswith("Unnamed"):
                st.write(f"  {i}. `{col_clean}` ⚠️ (Empty column)")
            elif "url" in col_clean.lower():
                st.write(f"  {i}. `{col_clean}` 🔗 (URL column)")
            elif "comment" in col_clean.lower():
                st.write(f"  {i}. `{col_clean}` 💬 (Comment column)")
            elif any(x in col_clean.lower() for x in ["status", "commented", "done", "posted"]):
                st.write(f"  {i}. `{col_clean}` ✅ (Status column)")
            else:
                st.write(f"  {i}. `{col_clean}`")
        
        # Show sample data
        if len(df) > 0:
            st.write("**Sample data (first 3 rows):**")
            st.dataframe(df.head(3), use_container_width=True)
            
            # Check for already commented rows
            status_cols = [col for col in df.columns if any(x in str(col).lower() for x in ["status", "commented", "done", "posted"])]
            if status_cols:
                status_col = status_cols[0]
                already_commented = df[status_col].astype(str).str.upper().str.strip().isin(["Y", "YES", "TRUE", "1"]).sum()
                if already_commented > 0:
                    st.warning(f"⚠️ {already_commented} rows are already marked as commented and will be skipped")
                else:
                    st.info("ℹ️ No rows are marked as already commented")
            
    except Exception as e:
        st.error(f"❌ Could not preview file: {e}")

# File preview
if uploaded_file:
    with st.expander("📁 File Preview", expanded=True):
        preview_columns(uploaded_file)

# Run button and processing
run_btn = st.button("🚀 Run Bot", disabled=st.session_state.get("processing", False))

def import_x_bot():
    """Enhanced bot import with better error handling"""
    candidates = [
        ("x_commenter_bot_fixed.py", ["XCommentBot"]),
        ("x_commenter_adapted.py", ["XCommentBot", "Bot"]),
        ("x_commenter_bot.py", ["XCommentBot", "Bot"]),
        ("twitter_commenter.py", ["TwitterCommentBot", "Bot"]),
    ]
    
    last_err = None
    for fname, class_names in candidates:
        path = Path(__file__).parent / fname
        if not path.exists():
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("x_bot_module", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["x_bot_module"] = mod
            spec.loader.exec_module(mod)
            
            for cname in class_names:
                if hasattr(mod, cname):
                    ui_log(f"✅ Successfully loaded {cname} from {fname}")
                    return getattr(mod, cname), fname
        except Exception as e:
            last_err = e
            ui_log(f"❌ Failed to load {fname}: {e}")
            continue
    
    if last_err:
        raise last_err
    raise FileNotFoundError("Could not find an X bot module. Expected one of: x_commenter_bot_fixed.py, x_commenter_adapted.py, x_commenter_bot.py, twitter_commenter.py")

if run_btn and uploaded_file:
    st.session_state["processing"] = True
    
    # Save upload locally so Selenium can read path
    local_path = Path("temp_upload" + (".csv" if uploaded_file.name.lower().endswith(".csv") else ".xlsx"))
    
    try:
        # Reset file pointer and save
        uploaded_file.seek(0)
        local_path.write_bytes(uploaded_file.read())
        ui_log(f"📁 Saved uploaded file to: {local_path}")
    except Exception as e:
        st.error(f"❌ Failed to save uploaded file: {e}")
        st.session_state["processing"] = False
        st.stop()

    # Progress tracking
    with progress_container:
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("🔄 Initializing bot...")

    st.info("🌐 Chrome will open ➜ sign in to X (Twitter). Keep this page open. You will see live logs below.")

    try:
        BotClass, fname = import_x_bot()
        ui_log(f"🤖 Loaded bot from {fname}")
        progress_bar.progress(10)
        status_text.text("🤖 Bot loaded successfully")
    except Exception as e:
        st.error(f"❌ Could not import your X bot: {e}")
        st.session_state["processing"] = False
        st.stop()

    # Instantiate bot with enhanced error handling
    try:
        progress_bar.progress(20)
        status_text.text("⚙️ Setting up bot configuration...")
        
        # Try different initialization signatures
        bot = None
        init_attempts = [
            lambda: BotClass(delay=delay, profile_path=profile or None, headless=headless),
            lambda: BotClass(delay=delay, profile_path=profile or None),
            lambda: BotClass(delay=delay),
            lambda: BotClass()
        ]
        
        for i, init_func in enumerate(init_attempts):
            try:
                bot = init_func()
                ui_log(f"✅ Bot initialized with method {i+1}")
                break
            except TypeError as e:
                ui_log(f"⚠️ Init method {i+1} failed: {e}")
                continue
        
        if bot is None:
            raise Exception("Could not initialize bot with any method")
            
        progress_bar.progress(30)
        status_text.text("✅ Bot configured successfully")
        
    except Exception as e:
        st.error(f"❌ Could not instantiate bot: {e}")
        st.session_state["processing"] = False
        st.stop()

    # Enhanced progress callback
    def progress_callback(message):
        """Enhanced progress callback with better UI updates"""
        ui_log(message)
        
        # Extract progress information if available
        if "post" in message.lower() and "/" in message:
            try:
                # Look for patterns like "Processing post 3/10" or "Completed 3/10 posts"
                parts = message.split()
                for part in parts:
                    if "/" in part:
                        current, total = part.split("/")
                        current = int(current)
                        total = int(total)
                        progress = min(30 + int((current / total) * 60), 90)
                        progress_bar.progress(progress)
                        status_text.text(f"🔄 Processing: {current}/{total} posts")
                        break
            except:
                pass
        elif "login" in message.lower():
            progress_bar.progress(40)
            status_text.text("🔐 Waiting for login...")
        elif "loading" in message.lower() or "spreadsheet" in message.lower():
            progress_bar.progress(50)
            status_text.text("📊 Loading spreadsheet...")
        elif "finished" in message.lower() or "completed" in message.lower():
            progress_bar.progress(100)
            status_text.text("✅ Processing completed!")

    # Run the bot with enhanced error handling
    exit_code = None
    try:
        progress_bar.progress(40)
        status_text.text("🚀 Starting bot execution...")
        
        # Try to call with UI support if available
        try:
            exit_code = bot.run(str(local_path), ui_mode=True, on_update=progress_callback)
        except TypeError:
            # Fallback for older bot versions
            ui_log("⚠️ Bot.run() does not support ui_mode; using legacy run() method.")
            exit_code = bot.run(str(local_path))
            
    except Exception as e:
        st.error(f"❌ Bot execution failed: {e}")
        ui_log(f"❌ Fatal error during bot execution: {e}")
        st.session_state["processing"] = False
        st.stop()

    # Process results with enhanced feedback
    progress_bar.progress(100)
    
    if exit_code == 0:
        st.success("🎉 **Success!** At least one comment was posted successfully. Check the processed file for 'Y' marks.")
        status_text.text("✅ Mission accomplished!")
    elif exit_code == 2:
        st.error("❌ **Login Failed:** Login wasn't detected in time. Please try again and make sure to log in to X.")
        status_text.text("❌ Login timeout")
    elif exit_code == 3:
        st.warning("⚠️ **No Comments Posted:** Ran successfully but posted 0 comments. Possible causes:")
        st.write("- All rows were already marked as 'Y' (commented)")
        st.write("- Column names didn't match expected format")
        st.write("- X blocked the actions or rate limited")
        st.write("- Network connectivity issues")
        status_text.text("⚠️ No comments posted")
    elif exit_code == 4:
        st.warning("⚠️ **Empty Dataset:** Your spreadsheet appears empty or had no valid rows to process.")
        status_text.text("⚠️ No data to process")
    elif isinstance(exit_code, int):
        st.error(f"❌ **Fatal Error:** An unexpected error occurred. Exit code: {exit_code}")
        st.write("Please check the logs below for detailed error information.")
        status_text.text(f"❌ Error (code: {exit_code})")
    else:
        st.info("ℹ️ **Finished:** Bot execution completed with unknown status.")
        status_text.text("ℹ️ Execution finished")

    # Show processed file info
    try:
        processed_files = list(Path.cwd().glob("processed_*.xlsx")) + list(Path.cwd().glob("processed_*.csv"))
        if processed_files:
            latest_file = max(processed_files, key=lambda x: x.stat().st_mtime)
            st.info(f"📄 **Processed file saved:** `{latest_file.name}`")
            
            # Show updated file preview
            with st.expander("📊 Updated File Preview", expanded=False):
                try:
                    if latest_file.suffix.lower() == ".csv":
                        df_updated = pd.read_csv(latest_file)
                    else:
                        df_updated = pd.read_excel(latest_file)
                    
                    st.write(f"**Updated file:** {latest_file.name}")
                    st.write(f"**Rows:** {len(df_updated)} | **Columns:** {len(df_updated.columns)}")
                    
                    # Show status column if exists
                    status_cols = [col for col in df_updated.columns if any(x in str(col).lower() for x in ["status", "commented", "done", "posted"])]
                    if status_cols:
                        status_col = status_cols[0]
                        completed = df_updated[status_col].astype(str).str.upper().str.strip().isin(["Y", "YES", "TRUE", "1"]).sum()
                        st.write(f"**Completed comments:** {completed}/{len(df_updated)}")
                    
                    st.dataframe(df_updated.head(), use_container_width=True)
                except Exception as e:
                    st.error(f"Could not preview updated file: {e}")
    except Exception:
        pass

    st.session_state["processing"] = False

# Footer with helpful information
st.markdown("---")
st.markdown("""
### 💡 Tips for Success:
- **Column Names:** Ensure your Excel/CSV has columns like 'postUrl', 'Generated comment', and 'Commented (Y/N)'
- **Login:** The bot will open Chrome - log in to X manually when prompted
- **Status Updates:** Successfully commented posts will be marked with 'Y' in the status column
- **Retry:** If some comments fail, you can run the bot again - it will skip already commented posts

### 🔧 Troubleshooting:
- **File Errors:** Make sure your Excel file isn't corrupted and has the right column names
- **Login Issues:** Clear your browser cache or try using a different Chrome profile
- **Rate Limiting:** If X blocks actions, wait a few minutes and try with a longer delay
""")

