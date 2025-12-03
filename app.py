# app.py
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta

# ---------------- Config ----------------
st.set_page_config(page_title="Excel Search App", layout="centered")

# Admin credentials
ADMIN_USER = "RSV"
ADMIN_PASS = "RSV@9328"

# Filenames used on the server (local)
SERVER_FILENAME = "uploaded_file.xlsx"   # stores uploaded file (or csv)
TIME_FILENAME = "upload_time.txt"        # stores IST upload time string

# ---------------- Helpers ----------------
def now_ist_str():
    ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist.strftime("%d-%m-%Y %H:%M:%S")

def save_upload_time(now_str: str):
    with open(TIME_FILENAME, "w", encoding="utf-8") as f:
        f.write(now_str)

def load_upload_time():
    if os.path.exists(TIME_FILENAME):
        try:
            return open(TIME_FILENAME, "r", encoding="utf-8").read()
        except:
            return "Unknown"
    return "No file uploaded yet"

def file_exists():
    return os.path.exists(SERVER_FILENAME)

def save_uploaded_file(uploaded_file):
    # Save uploaded file bytes to SERVER_FILENAME (overwrite)
    with open(SERVER_FILENAME, "wb") as f:
        f.write(uploaded_file.getbuffer())

def remove_file():
    if file_exists():
        os.remove(SERVER_FILENAME)
    if os.path.exists(TIME_FILENAME):
        os.remove(TIME_FILENAME)

def load_dataframe():
    if not file_exists():
        return None
    # Try excel then csv
    try:
        df = pd.read_excel(SERVER_FILENAME, engine="openpyxl")
    except Exception:
        try:
            df = pd.read_csv(SERVER_FILENAME)
        except Exception:
            return None
    return df

# ---------------- Session ----------------
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "mode" not in st.session_state:
    st.session_state.mode = "guest"  # default to guest

# ---------------- UI ----------------
st.title("Excel Search App")

# Top choices: Guest / Admin
col1, col2 = st.columns([1,1])
with col1:
    if st.button("Guest"):
        st.session_state.mode = "guest"
with col2:
    if st.button("Admin"):
        st.session_state.mode = "admin_login"

st.markdown("---")

# ---------------- Admin Login ----------------
if st.session_state.mode == "admin_login":
    st.subheader("Admin Login")
    if not st.session_state.admin_logged_in:
        username = st.text_input("ID")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == ADMIN_USER and password == ADMIN_PASS:
                st.session_state.admin_logged_in = True
                st.session_state.mode = "admin"
                st.success("Logged in as Admin.")
                st.rerun()
            else:
                st.error("Invalid credentials.")
    else:
        st.session_state.mode = "admin"
        st.rerun()

# ---------------- Admin Panel ----------------
if st.session_state.mode == "admin":
    st.subheader("Admin Panel (Upload / Delete)")
    st.markdown(f"**Last Upload:** {load_upload_time()}")

    # Show preview if file exists
    if file_exists():
        df_preview = load_dataframe()
        if df_preview is not None:
            st.write("Preview (first 10 rows):")
            st.dataframe(df_preview.head(10))
        else:
            st.warning("Current file exists but couldn't be read (maybe corrupted).")

    # Upload new file (this will overwrite SERVER_FILENAME)
    st.markdown("#### Upload new file (this will overwrite the existing file)")
    uploaded = st.file_uploader("Choose an Excel (.xlsx/.xls) or CSV (.csv)", type=["xlsx","xls","csv"], key="admin_uploader")
    if uploaded is not None:
        save_uploaded_file(uploaded)
        save_upload_time(now_ist_str())
        st.success("File uploaded and saved on server. It will remain until manually deleted by Admin.")
        st.rerun()

    # Manual delete
    if file_exists():
        if st.button("Delete current file"):
            remove_file()
            st.success("File deleted by Admin.")
            st.rerun()

    # Admin search (optional)
    st.markdown("---")
    st.subheader("Admin Search")
    df_admin = load_dataframe()
    if df_admin is None:
        st.info("No file to search. Upload an Excel or CSV above.")
    else:
        q = st.text_input("Search (admin)", key="admin_search")
        cols_choice = st.multiselect("Columns to display (optional)", options=list(df_admin.columns))
        if st.button("Search (Admin)"):
            mask = df_admin.apply(lambda row: row.astype(str).str.contains(str(q), case=False, na=False).any(), axis=1)
            res = df_admin[mask]
            if res.empty:
                st.warning("No matching rows found.")
            else:
                st.success(f"{len(res)} matching rows found.")
                if cols_choice:
                    st.dataframe(res[cols_choice])
                else:
                    st.dataframe(res)

    if st.button("Logout Admin"):
        st.session_state.admin_logged_in = False
        st.session_state.mode = "guest"
        st.rerun()

# ---------------- Guest Screen ----------------
if st.session_state.mode == "guest":
    st.subheader("Guest Search (no login required)")
    st.markdown(f"**Last Upload:** {load_upload_time()}")

    df = load_dataframe()
    if df is None:
        st.warning("No file uploaded yet. Ask Admin to upload.")
    else:
        query = st.text_input("Search (partial, case-insensitive)", key="guest_search")
        cols_choice = st.multiselect("Columns to display (optional)", options=list(df.columns))
        if st.button("SUBMIT"):
            mask = df.apply(lambda row: row.astype(str).str.contains(str(query), case=False, na=False).any(), axis=1)
            result = df[mask]
            if result.empty:
                st.warning("No matching rows found.")
            else:
                st.success(f"{len(result)} matching rows found.")
                if cols_choice:
                    st.dataframe(result[cols_choice])
                else:
                    st.dataframe(result)
        else:
            st.info("Type a search term and press SUBMIT.")

