import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="Material Search", layout="centered")

EXCEL_FILE = "uploaded_file.xlsx"
TIME_FILE = "upload_time.txt"

ADMIN_USER = "RSV"
ADMIN_PASS = "RSV@9328"

# -------------------------------
# Load Excel
# -------------------------------
def load_excel():
    if os.path.exists(EXCEL_FILE):
        return pd.read_excel(EXCEL_FILE)
    return None

# -------------------------------
# Save Upload Time (IST)
# -------------------------------
def save_upload_time():
    # Get UTC time, convert to IST (UTC+5:30)
    ist_time = (datetime.utcnow() + timedelta(hours=5, minutes=30))
    now = ist_time.strftime("%d-%m-%Y %H:%M:%S")

    with open(TIME_FILE, "w") as f:
        f.write(now)

def load_upload_time():
    if os.path.exists(TIME_FILE):
        return open(TIME_FILE, "r").read()
    return "No file uploaded yet"

# -------------------------------
# Top Navigation (Guest / Admin)
# -------------------------------
def top_nav():
    col1, col2, col3 = st.columns([1, 1, 6])
    with col1:
        if st.button("Guest"):
            st.session_state["mode"] = "guest"
    with col2:
        if st.button("Admin"):
            st.session_state["mode"] = "admin_login"

# -------------------------------
# Guest Screen
# -------------------------------
def guest_screen():
    st.markdown("<h2 style='text-align:center;'>Guest Search</h2>", unsafe_allow_html=True)

    upload_time = load_upload_time()
    st.markdown(f"<p style='text-align:center; font-size:18px;'>📅 Last Upload: <b>{upload_time}</b></p>",
                unsafe_allow_html=True)

    df = load_excel()
    if df is None:
        st.warning("No Excel file uploaded yet.")
        return

    st.write("")

    search_value = st.text_input("", placeholder="Enter text to search", key="guest_search")
    if st.button("SUBMIT"):
        result = df[df.apply(lambda row: row.astype(str).str.contains(search_value, case=False).any(), axis=1)]

        if result.empty:
            st.error("No matching data found.")
        else:
            st.success("Match found:")
            st.dataframe(result)

# -------------------------------
# Admin Login Screen
# -------------------------------
def admin_login():
    st.markdown("<h2 style='text-align:center;'>Admin Login</h2>", unsafe_allow_html=True)

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username == ADMIN_USER and password == ADMIN_PASS:
            st.session_state["mode"] = "admin_panel"
        else:
            st.error("Incorrect username or password.")

# -------------------------------
# Admin Panel
# -------------------------------
def admin_panel():
    st.markdown("<h2 style='text-align:center;'>Admin Panel</h2>", unsafe_allow_html=True)

    upload_time = load_upload_time()
    st.markdown(f"<p style='text-align:center; font-size:18px;'>📅 Last Upload: <b>{upload_time}</b></p>",
                unsafe_allow_html=True)

    st.subheader("Upload New Excel File")
    uploaded = st.file_uploader("Choose Excel file", type=["xlsx"])

    if uploaded:
        with open(EXCEL_FILE, "wb") as f:
            f.write(uploaded.read())
        save_upload_time()
        st.success("File uploaded successfully!")

    st.subheader("Delete Current Excel File")
    if st.button("Delete File"):
        if os.path.exists(EXCEL_FILE):
            os.remove(EXCEL_FILE)
        if os.path.exists(TIME_FILE):
            os.remove(TIME_FILE)
        st.warning("File deleted successfully!")

    st.subheader("Search (Admin)")
    df = load_excel()
    if df is not None:
        search_admin = st.text_input("Search", key="admin_search")
        if st.button("Admin Submit"):
            result = df[df.apply(lambda row: row.astype(str).str.contains(search_admin, case=False).any(), axis=1)]
            if result.empty:
                st.error("No matching data found.")
            else:
                st.dataframe(result)

# -------------------------------
# MAIN APP LOGIC
# -------------------------------
if "mode" not in st.session_state:
    st.session_state["mode"] = "guest"  # Default mode

top_nav()

if st.session_state["mode"] == "guest":
    guest_screen()
elif st.session_state["mode"] == "admin_login":
    admin_login()
elif st.session_state["mode"] == "admin_panel":
    admin_panel()
