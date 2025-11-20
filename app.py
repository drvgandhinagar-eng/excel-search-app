# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ---------------- Config ----------------
ADMIN_USERNAME = "RSV"  # exact username you provided earlier
ADMIN_PASSWORD = "RSV@9328"

UPLOAD_PATH = "current.xlsx"  # server filename (will store uploaded bytes here)

# ---------------- Helpers ----------------
def file_exists():
    return os.path.exists(UPLOAD_PATH)

def load_dataframe():
    if not file_exists():
        return None
    # Try Excel first, then CSV
    try:
        df = pd.read_excel(UPLOAD_PATH, engine="openpyxl")
    except Exception:
        try:
            df = pd.read_csv(UPLOAD_PATH)
        except Exception:
            return None
    return df

def save_uploaded_file(uploaded_file):
    # Save uploaded file to UPLOAD_PATH (overwrite)
    with open(UPLOAD_PATH, "wb") as f:
        f.write(uploaded_file.getbuffer())

def remove_file():
    if file_exists():
        os.remove(UPLOAD_PATH)

def get_file_info():
    if not file_exists():
        return None
    stat = os.stat(UPLOAD_PATH)
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    size_kb = stat.st_size // 1024
    df = load_dataframe()
    if df is not None:
        shape = f"{df.shape[0]} rows × {df.shape[1]} columns"
    else:
        shape = ""
    return {"modified": mtime, "size_kb": size_kb, "shape": shape}

# ---------------- Session state ----------------
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

# ---------------- UI ----------------
st.set_page_config(page_title="Excel Search App", layout="wide")
st.title("Excel Search App")

st.markdown("Choose your mode and proceed:")
mode = st.radio("", ("Guest", "Admin"), horizontal=True)
st.markdown("---")

file_info = get_file_info()

# ----- ADMIN FLOW -----
if mode == "Admin":
    st.subheader("Admin Panel")
    if not st.session_state.admin_logged_in:
        st.info("Enter admin credentials to upload or delete the dataset.")
        col1, col2 = st.columns([2,1])
        with col1:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
        with col2:
            if st.button("Login"):
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.success("Admin logged in.")
                    st.experimental_rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        st.success(f"Logged in as admin: {ADMIN_USERNAME}")
        # Show file info
        st.markdown("#### Current file info")
        if file_info:
            st.info(
                f"**Uploaded On:** {file_info['modified']}  \n"
                f"**File Size:** {file_info['size_kb']} KB  \n"
                f"**Shape:** {file_info['shape']}"
            )
            # preview
            df_preview = load_dataframe()
            if df_preview is not None:
                st.write("Preview (first 10 rows):")
                st.dataframe(df_preview.head(10))
            else:
                st.warning("Could not load preview (file unreadable).")
        else:
            st.warning("No file is uploaded currently.")

        st.markdown("#### Upload new file (this will replace the current file)")
        uploaded_file = st.file_uploader("Upload Excel (.xlsx, .xls) or CSV (.csv)", type=["xlsx","xls","csv"], key="admin_uploader")
        if uploaded_file is not None:
            save_uploaded_file(uploaded_file)
            st.success("File uploaded and saved (replaced any existing file).")
            st.experimental_rerun()

        if file_exists():
            if st.button("Delete current file"):
                remove_file()
                st.success("File deleted by admin.")
                st.experimental_rerun()

        if st.button("Logout"):
            st.session_state.admin_logged_in = False
            st.experimental_rerun()

# ----- GUEST FLOW -----
else:
    st.subheader("Guest (Search only)")
    st.info("Guests can search the uploaded file. Guests cannot upload or delete files.")

    st.markdown("#### Current file info")
    if file_info:
        st.info(
            f"**Uploaded On:** {file_info['modified']}  \n"
            f"**File Size:** {file_info['size_kb']} KB  \n"
            f"**Shape:** {file_info['shape']}"
        )
    else:
        st.warning("No file uploaded yet. Please ask Admin to upload a file.")

    df = load_dataframe()
    if df is None:
        st.stop()

    query = st.text_input("Search for text or number (partial match, case-insensitive)", key="guest_search")
    cols_to_show = st.multiselect("Columns to display (optional)", options=list(df.columns))

    if query:
        mask = df.apply(lambda row: row.astype(str).str.contains(str(query), case=False, na=False).any(), axis=1)
        result = df[mask]
        if result.empty:
            st.warning("No matching rows found.")
        else:
            st.success(f"{len(result)} matching row(s) found.")
            if cols_to_show:
                st.dataframe(result[cols_to_show])
            else:
                st.dataframe(result)
    else:
        st.info("Type a search term to find matching rows.")

