# app.py
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
st.set_page_config(page_title="Material Search (Versioned)", layout="centered")

ADMIN_USER = "RSV"
ADMIN_PASS = "RSV@9328"

# naming
REMOTE_FILE_PREFIX = "file_"             # files: file_20251121_164510.xlsx
REMOTE_TIME = "upload_time.txt"          # stores IST string for latest upload time
LATEST_POINTER = "latest_version.txt"    # stores current latest filename
LOCAL_FILE = "latest_download.xlsx"      # local downloaded file for searching

# ---------------------------
# HELPERS: time
# ---------------------------
def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def now_ist_str():
    return now_ist().strftime("%d-%m-%Y %H:%M:%S")

def filename_from_now(ext="xlsx"):
    # use human-friendly timestamp YYYYMMDD_HHMMSS so names sort lexicographically
    ts = now_ist().strftime("%Y%m%d_%H%M%S")
    return f"{REMOTE_FILE_PREFIX}{ts}.{ext}"

# ---------------------------
# FIREBASE INIT
# ---------------------------
def init_firebase():
    if firebase_admin._apps:
        return

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        svc_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if not svc_json:
            st.error("Missing Firebase credentials. Set FIREBASE_SERVICE_ACCOUNT (env) or GOOGLE_APPLICATION_CREDENTIALS (local).")
            st.stop()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(svc_json.encode("utf-8"))
        tmp.close()
        cred = credentials.Certificate(tmp.name)

    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "material-excel.appspot.com")
    firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})

def get_bucket():
    init_firebase()
    return storage.bucket()

# ---------------------------
# FIREBASE file ops (versioned)
# ---------------------------
def upload_new_version(file_bytes, original_filename=None):
    """
    Upload bytes as a new versioned filename. Returns the created filename.
    """
    bucket = get_bucket()
    # choose extension from original filename if possible
    ext = "xlsx"
    if original_filename and "." in original_filename:
        ext = original_filename.split(".")[-1]
    remote_name = filename_from_now(ext=ext)
    blob = bucket.blob(remote_name)
    blob.upload_from_string(file_bytes, content_type="application/octet-stream")
    # update pointer and upload time
    bucket.blob(LATEST_POINTER).upload_from_string(remote_name)
    bucket.blob(REMOTE_TIME).upload_from_string(now_ist_str())
    return remote_name

def download_latest_to_local(local_path=LOCAL_FILE):
    bucket = get_bucket()
    ptr_blob = bucket.blob(LATEST_POINTER)
    if not ptr_blob.exists():
        return False
    latest_name = ptr_blob.download_as_text()
    blob = bucket.blob(latest_name)
    if not blob.exists():
        return False
    blob.download_to_filename(local_path)
    return True

def list_versions(limit=1000):
    """
    Return list of dicts: [{'name': blob.name, 'time_created': blob.time_created}, ...]
    sorted descending by time_created (newest first).
    Excludes pointer/time files.
    """
    bucket = get_bucket()
    blobs = list(bucket.list_blobs())
    files = []
    for b in blobs:
        n = b.name
        if n in (LATEST_POINTER, REMOTE_TIME):
            continue
        if n.startswith(REMOTE_FILE_PREFIX):
            files.append({"name": n, "time_created": b.time_created})
    # sort newest first
    files.sort(key=lambda x: x["time_created"] or datetime.min, reverse=True)
    return files

def download_specific_version(version_name, local_path):
    bucket = get_bucket()
    blob = bucket.blob(version_name)
    if not blob.exists():
        return False
    blob.download_to_filename(local_path)
    return True

def delete_version(version_name):
    bucket = get_bucket()
    blob = bucket.blob(version_name)
    if blob.exists():
        blob.delete()
    # if this was the latest pointer, update pointer to the newest remaining (or remove)
    ptr_blob = bucket.blob(LATEST_POINTER)
    if ptr_blob.exists():
        current_latest = ptr_blob.download_as_text()
        if current_latest == version_name:
            remaining = list_versions()
            if remaining:
                new_latest = remaining[0]["name"]
                ptr_blob.upload_from_string(new_latest)
                # update upload_time to that file's creation time (format IST)
                try:
                    new_blob = bucket.blob(new_latest)
                    t = new_blob.time_created
                    # convert to IST string
                    ist = (t - timedelta(0)) + timedelta(hours=5, minutes=30) if isinstance(t, datetime) else now_ist()
                    ptr_time = ist.strftime("%d-%m-%Y %H:%M:%S")
                except Exception:
                    ptr_time = now_ist_str()
                bucket.blob(REMOTE_TIME).upload_from_string(ptr_time)
            else:
                ptr_blob.delete()
                bucket.blob(REMOTE_TIME).upload_from_string("")  # clear

def load_latest_upload_time():
    bucket = get_bucket()
    blob = bucket.blob(REMOTE_TIME)
    if not blob.exists():
        return "No file uploaded yet"
    return blob.download_as_text() or "No file uploaded yet"

# ---------------------------
# STREAMLIT UI
# ---------------------------

if "mode" not in st.session_state:
    st.session_state["mode"] = "guest"

# top buttons
c1, c2, _ = st.columns([1,1,6])
with c1:
    if st.button("Guest"):
        st.session_state["mode"] = "guest"
with c2:
    if st.button("Admin"):
        st.session_state["mode"] = "admin_login"

st.title("Material Search — Versioned Files")

# Ensure Firebase initialized early (will stop with message if not configured)
try:
    init_firebase()
except Exception as e:
    st.error("Firebase init error: " + str(e))
    st.stop()

# GUEST
if st.session_state["mode"] == "guest":
    st.subheader("Guest Search")
    st.markdown(f"**Last Upload:** {load_latest_upload_time()}")

    ok = download_latest_to_local()
    if not ok:
        st.warning("No file available. Ask admin to upload.")
    else:
        try:
            df = pd.read_excel(LOCAL_FILE, engine="openpyxl")
        except Exception:
            try:
                df = pd.read_csv(LOCAL_FILE)
            except Exception:
                st.error("Failed to read the file. Ask admin to re-upload.")
                st.stop()
        query = st.text_input("", placeholder="Enter text to search")
        if st.button("SUBMIT"):
            res = df[df.apply(lambda row: row.astype(str).str.contains(str(query), case=False, na=False).any(), axis=1)]
            if res.empty:
                st.warning("No matching rows found.")
            else:
                st.success(f"{len(res)} row(s) found")
                st.dataframe(res)

# ADMIN - login
elif st.session_state["mode"] == "admin_login":
    st.subheader("Admin Login")
    user = st.text_input("ID")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state["mode"] = "admin_panel"
            st.rerun()
        else:
            st.error("Incorrect credentials")

# ADMIN panel
elif st.session_state["mode"] == "admin_panel":
    st.subheader("Admin Panel")
    st.markdown(f"**Last Upload:** {load_latest_upload_time()}")

    st.markdown("### Upload new version (old versions will be kept)")
    uploaded = st.file_uploader("Choose Excel (.xlsx) or CSV", type=["xlsx","csv"])
    if uploaded:
        b = uploaded.getvalue()
        created_name = upload_new_version(b, original_filename=uploaded.name)
        st.success(f"Uploaded as: {created_name}")
        st.rerun()

    st.markdown("---")
    st.markdown("### Versions (newest first)")
    versions = list_versions()
    if not versions:
        st.info("No versions found.")
    else:
        names = [v["name"] + "  —  " + (v["time_created"].strftime("%d-%m-%Y %H:%M:%S") if v["time_created"] else "") for v in versions]
        sel = st.selectbox("Select a version to preview or delete", options=[v["name"] for v in versions], format_func=lambda x: x)
        st.markdown("#### Preview selected version")
        if st.button("Download & Preview Selected Version"):
            ok = download_specific_version(sel, LOCAL_FILE)
            if not ok:
                st.error("Failed to download that version.")
            else:
                try:
                    dfv = pd.read_excel(LOCAL_FILE, engine="openpyxl")
                except Exception:
                    try:
                        dfv = pd.read_csv(LOCAL_FILE)
                    except Exception:
                        st.error("Cannot parse file.")
                        dfv = None
                if dfv is not None:
                    st.dataframe(dfv.head(50))

        st.markdown("#### Delete selected version")
        if st.button("Delete Selected Version"):
            delete_version(sel)
            st.success(f"Deleted: {sel}")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Admin quick search on latest")
    ok = download_latest_to_local()
    if ok:
        try:
            df_latest = pd.read_excel(LOCAL_FILE, engine="openpyxl")
        except Exception:
            try:
                df_latest = pd.read_csv(LOCAL_FILE)
            except Exception:
                df_latest = None
        if df_latest is not None:
            q = st.text_input("Search (admin)", key="admin_search")
            if st.button("Search (Admin)"):
                res = df_latest[df_latest.apply(lambda row: row.astype(str).str.contains(str(q), case=False, na=False).any(), axis=1)]
                if res.empty:
                    st.warning("No matches")
                else:
                    st.dataframe(res)
