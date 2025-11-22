import streamlit as st
import pandas as pd
import os
import json
import tempfile
from datetime import datetime, timedelta

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, storage

# ---------------------------
# CONFIG
# ---------------------------
st.set_page_config(page_title="Material Search", layout="centered")

ADMIN_USER = "RSV"
ADMIN_PASS = "RSV@9328"

REMOTE_FILE = "uploaded_file.xlsx"
REMOTE_TIME = "upload_time.txt"

LOCAL_FILE = "latest.xlsx"


# ---------------------------
# INIT FIREBASE
# ---------------------------
def init_firebase():
    if firebase_admin._apps:
        return

    # 1) Try GOOGLE_APPLICATION_CREDENTIALS (local testing)
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # 2) Use Render env var FIREBASE_SERVICE_ACCOUNT (JSON string)
        svc_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if not svc_json:
            st.error("Missing Firebase credentials. Set FIREBASE_SERVICE_ACCOUNT.")
            st.stop()

        # Write JSON string to a temporary file
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        temp.write(svc_json.encode("utf-8"))
        temp.close()
        cred = credentials.Certificate(temp.name)

    # Storage bucket name
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "material-excel.appspot.com")

    firebase_admin.initialize_app(cred, {
        "storageBucket": bucket_name
    })


# ---------------------------
# FIREBASE STORAGE HELPERS
# ---------------------------
def get_bucket():
    init_firebase()
    return storage.bucket()


def upload_file_to_firebase(file_bytes):
    bucket = get_bucket()

    # delete old file
    blob = bucket.blob(REMOTE_FILE)
    if blob.exists():
        blob.delete()

    # upload new file
    blob.upload_from_string(file_bytes, content_type="application/octet-stream")


def download_file_from_firebase():
    bucket = get_bucket()
    blob = bucket.blob(REMOTE_FILE)

    if not blob.exists():
        return False

    blob.download_to_filename(LOCAL_FILE)
    return True


def delete_remote_file():
    bucket = get_bucket()
    blob = bucket.blob(REMOTE_FILE)
    if blob.exists():
        blob.delete()


def save_upload_time():
    bucket = get_bucket()
    ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    blob = bucket.blob(REMOTE_TIME)
    blob.upload_from_string(ist.strftime("%d-%m-%Y %H:%M:%S"))


def load_upload_time():
    bucket = get_bucket()
    blob = bucket.blob(REMOTE_TIME)

    if not blob.exists():
        return "No file uploaded yet"

    return blob.download_as_text()


# ---------------------------
# PAGE LOGIC
# ---------------------------
def guest_screen():
    st.subheader("Guest Search")

    st.markdown(f"**Last Upload:** {load_upload_time()}")

    if not download_file_from_firebase():
        st.warning("No file uploaded yet")
        return

    try:
        df = pd.read_excel(LOCAL_FILE)
    except:
        st.error("File corrupted — ask admin to reupload.")
        return

    query = st.text_input("", placeholder="Enter text to search")

    if st.button("SUBMIT"):
        result = df[df.apply(lambda row: row.astype(str).str.contains(query, case=False).any(), axis=1)]
        if result.empty:
            st.warning("No matching data found.")
        else:
            st.dataframe(result)


def admin_login():
    st.subheader("Admin Login")
    user = st.text_input("ID")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state["mode"] = "admin"
            st.experimental_rerun()
        else:
            st.error("Incorrect credentials")


def admin_panel():
    st.subheader("Admin Panel")

    st.markdown(f"**Last Upload:** {load_upload_time()}")

    uploaded = st.file_uploader("Upload Excel", type=["xlsx"])
    if uploaded:
        upload_file_to_firebase(uploaded.getvalue())
        save_upload_time()
        st.success("File uploaded successfully!")
        st.experimental_rerun()

    if st.button("Delete File"):
        delete_remote_file()
        st.warning("File deleted!")
        st.experimental_rerun()

    # Search
    if download_file_from_firebase():
        df = pd.read_excel(LOCAL_FILE)
        st.subheader("Admin Search")
        q = st.text_input("Search")
        if st.button("Search (Admin)"):
            result = df[df.apply(lambda row: row.astype(str).str.contains(q, case=False).any(), axis=1)]
            st.dataframe(result)


# ---------------------------
# MAIN
# ---------------------------
if "mode" not in st.session_state:
    st.session_state["mode"] = "guest"

# TOP BUTTONS
c1, c2, _ = st.columns([1, 1, 6])
with c1:
    if st.button("Guest"):
        st.session_state["mode"] = "guest"
with c2:
    if st.button("Admin"):
        st.session_state["mode"] = "login"

# ROUTING
if st.session_state["mode"] == "guest":
    guest_screen()
elif st.session_state["mode"] == "login":
    admin_login()
elif st.session_state["mode"] == "admin":
    admin_panel()
