import sys, os, importlib, inspect
import streamlit as st
from pathlib import Path
import pandas as pd

# Prefer local dir for imports
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(page_title="X Auto Commenter", page_icon="🧵", layout="centered")
st.title("🧵 X (Twitter) Auto Commenter – Easy UI")

uploaded_file = st.file_uploader("1️⃣ Upload your Excel/CSV", type=["xlsx", "csv"])
delay = st.slider("2️⃣ Delay between comments (seconds)", 0.5, 5.0, 1.5, 0.1)
profile = st.text_input("3️⃣ (Optional) Chrome profile folder")
headless = st.checkbox("Run headless (no visible browser)", value=False)

run_btn = st.button("🚀 Run bot")
log_box = st.empty()

def ui_log(msg: str) -> None:
    prev = st.session_state.get("logs", [])
    prev.append(str(msg))
    st.session_state["logs"] = prev[-200:]
    log_box.markdown("```\n" + "\n".join(st.session_state["logs"]) + "\n```")

# Small helper to preview the columns before running
def preview_columns(file):
    try:
        if file.name.lower().endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file, sheet_name=0)
        st.caption(f"Detected columns: {list(df.columns)} (rows: {len(df)})")
    except Exception as e:
        st.caption(f"Could not preview file: {e}")

if uploaded_file:
    preview_columns(uploaded_file)

# Dynamically import the X bot module from the working folder
def import_x_bot():
    candidates = [
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
                    return getattr(mod, cname), fname
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise FileNotFoundError("Could not find an X bot module. Expected one of: x_commenter_adapted.py, x_commenter.py, twitter_commenter.py")

if run_btn and uploaded_file:
    # Save upload locally so Selenium can read path
    local_path = Path("temp_upload" + (".csv" if uploaded_file.name.lower().endswith(".csv") else ".xlsx"))
    local_path.write_bytes(uploaded_file.read())

    st.info("Chrome will open ➜ sign in to X (Twitter). Keep this page open. You will see live logs below.")

    try:
        BotClass, fname = import_x_bot()
        ui_log(f"Loaded bot from {fname}")
    except Exception as e:
        st.error(f"❌ Could not import your X bot: {e}")
        st.stop()

    # Instantiate bot
    try:
        bot = BotClass(delay=delay, profile_path=profile or None, headless=headless)
    except TypeError:
        try:
            bot = BotClass(delay=delay, profile_path=profile or None)
        except TypeError:
            try:
                bot = BotClass()
            except Exception as e:
                st.error(f"❌ Could not instantiate bot: {e}")
                st.stop()

    # Inspect run() signature to decide how to call it
    try:
        sig = inspect.signature(getattr(BotClass, "run"))
        ui_log(f"Bot.run signature: {sig}")
    except Exception as e:
        ui_log(f"Could not inspect run(): {e}")

    # Try to call with UI support if available; fallback to legacy signature
    exit_code = None
    try:
        exit_code = bot.run(str(local_path), ui_mode=True, on_update=ui_log)
    except TypeError:
        try:
            ui_log("Bot.run() does not support ui_mode; using legacy run() with UI patches.")
            exit_code = bot.run(str(local_path))
        except Exception as e:
            st.error(f"❌ Bot.run failed: {e}")
            st.stop()
    except Exception as e:
        st.error(f"❌ Bot.run error: {e}")
        st.stop()

    # Interpret common exit codes
    if exit_code == 0:
        st.success("🎉 Done: at least one comment was posted. Check the sheet for 'Y' marks (if your bot writes them).")
    elif exit_code == 2:
        st.error("❌ Login wasn’t detected in time. Please try again.")
    elif exit_code == 3:
        st.warning("⚠️ Ran, but posted 0 comments. Likely causes: all rows were already 'Y', columns didn't match, or X blocked the actions. See the log below.")
    elif exit_code == 4:
        st.warning("⚠️ Your sheet appears empty or had no valid rows.")
    elif isinstance(exit_code, int):
        st.error(f"❌ A fatal error occurred. Exit code: {exit_code}. Scroll the log for details.")
    else:
        st.info("Finished. (Unknown exit code from bot)")
