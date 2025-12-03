# app.py  -- Firebase-backed, timestamped versioning Streamlit app
import streamlit as st
import pandas as pd
import os
import tempfile
import json
from datetime import datetime, timedelta

# Firebase Admin imports
import firebase_admin
from firebase_admin import credentials, storage

# -----------------------
# Small helper: load secrets into env (Streamlit secrets TOML -> env)
# -----------------------
try:
    # If using Streamlit Secrets (TOML with [FIREBASE])
    if "FIREBASE" in st.secrets:
        fb = st.secrets["FIREBASE"]
        if "SERVICE_ACCOUNT" in fb:
            os.environ["FIREBASE_SERVICE_ACCOUNT"] = fb["SERVICE_ACCOUNT"]
        if "STORAGE_BUCKET" in fb:
            os.environ["FIREBASE_STORAGE_BUCKET"] = fb["STORAGE_BUCKET"]
except Exception:
    # If st.secrets not available or key missing, ignore and fall back to env vars
    pass

# -----------------------
# Config
# -----------------------
st.set_page_config(page_title="Material Search — Firebase Versioned", layout="centered")

ADMIN_USER = "RSV"
ADMIN_PASS = "RSV@9328"

REMOTE_PREFIX = "file_"              # versioned files like file_20251121_164510.xlsx
LATEST_POINTER = "latest_version.txt"
UPLOAD_TIME_FILE = "upload_time.txt"
LOCAL_DOWNLOAD = "latest_download.xlsx"

# -----------------------
# Time helpers (IST)
# -----------------------
def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def now_ist_str():
    return now_ist().strftime("%d-%m-%Y %H:%M:%S")

def timestamp_for_filename():
    return now_ist().strftime("%Y%m%d_%H%M%S")

# -----------------------
# Firebase initialization
# -----------------------
def init_firebase():
    if firebase_admin._apps:
        return

    # try GOOGLE_APPLICATION_CREDENTIALS file path first (local testing)
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # try FIREBASE_SERVICE_ACCOUNT env var (or set via st.secrets)
        svc_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        if not svc_json:
            st.error("Missing Firebase credentials. Set FIREBASE_SERVICE_ACCOUNT in env or use Streamlit Secrets.")
            st.stop()
        # write JSON to temp file for admin SDK
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(svc_json.encode("utf-8"))
        tmp.close()
        cred = credentials.Certificate(tmp.name)

    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET") or os.environ.get("FIREBASE_STORAGE_BUCKET".upper()) or None
    if not bucket_name:
        # common default pattern
        # try to derive from project id in JSON if possible
        try:
            data = json.loads(svc_json)
            pid = data.get("project_id")
            if pid:
                bucket_name = f"{pid}.appspot.com"
        except Exception:
            bucket_name = None

    if bucket_name:
        firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
    else:
        firebase_admin.initialize_app(cred)

def get_bucket():
    init_firebase()
    return storage.bucket()

# -----------------------
# Firebase operations (versioned)
# -----------------------
def make_versioned_filename(original_name):
    ext = "xlsx"
    if original_name and "." in original_name:
        ext = original_name.split(".")[-1]
    return f"{REMOTE_PREFIX}{timestamp_for_filename()}.{ext}"

def upload_new_version(file_bytes, original_name=None):
    bucket = get_bucket()
    remote_name = make_versioned_filename(original_name)
    blob = bucket.blob(remote_name)
    blob.upload_from_string(file_bytes, content_type="application/octet-stream")
    # write pointer and upload time
    bucket.blob(LATEST_POINTER).upload_from_string(remote_name)
    bucket.blob(UPLOAD_TIME_FILE).upload_from_string(now_ist_str())
    return remote_name

def download_pointer():
    bucket = get_bucket()
    ptr = bucket.blob(LATEST_POINTER)
    if not ptr.exists():
        return None
    return ptr.download_as_text()

def download_latest_to_local(local_path=LOCAL_DOWNLOAD):
    bucket = get_bucket()
    latest = download_pointer()
    if not latest:
        return False
    blob = bucket.blob(latest)
    if not blob.exists():
        return False
    blob.download_to_filename(local_path)
    return True

def list_versions():
    bucket = get_bucket()
    blobs = list(bucket.list_blobs())
    files = []
    for b in blobs:
        name = b.name
        if name in (LATEST_POINTER, UPLOAD_TIME_FILE):
            continue
        if name.startswith(REMOTE_PREFIX):
            files.append({"name": name, "time_created": b.time_created})
    files.sort(key=lambda x: x["time_created"] or datetime.min, reverse=True)
    return files

def download_specific_version(name, local_path=LOCAL_DOWNLOAD):
    bucket = get_bucket()
    blob = bucket.blob(name)
    if not blob.exists():
        return False
    blob.download_to_filename(local_path)
    return True

def delete_version(name):
    bucket = get_bucket()
    blob = bucket.blob(name)
    if blob.exists():
        blob.delete()
    # if deleted file was latest, update pointer
    ptr = bucket.blob(LATEST_POINTER)
    if ptr.exists():
        current = ptr.download_as_text()
        if current == name:
            remaining = list_versions()
            if remaining:
                new_latest = remaining[0]["name"]
                ptr.upload_from_string(new_latest)
                # set upload time to that blob's time_created converted to IST string
                try:
                    new_blob = bucket.blob(new_latest)
                    t = new_blob.time_created
                    if isinstance(t, datetime):
                        ist = t + timedelta(hours=5, minutes=30)
                        bucket.blob(UPLOAD_TIME_FILE).upload_from_string(ist.strftime("%d-%m-%Y %H:%M:%S"))
                    else:
                        bucket.blob(UPLOAD_TIME_FILE).upload_from_string(now_ist_str())
                except Exception:
                    bucket.blob(UPLOAD_TIME_FILE).upload_from_string(now_ist_str())
            else:
                ptr.delete()
                bucket.blob(UPLOAD_TIME_FILE).upload_from_string("")

def load_upload_time():
    bucket = get_bucket()
    blob = bucket.blob(UPLOAD_TIME_FILE)
    if not blob.exists():
        return "No file uploaded yet"
    txt = blob.download_as_text()
    return txt if txt else "No file uploaded yet"

# -----------------------
# Streamlit UI & logic
# -----------------------
if "mode" not in st.session_state:
    st.session_state["mode"] = "guest"

st.title("Material Search — Versioned Files (Firebase)")

# top nav
c1, c2, _ = st.columns([1,1,6])
with c1:
    if st.button("Guest"):
        st.session_state["mode"] = "guest"
with c2:
    if st.button("Admin"):
        st.session_state["mode"] = "admin_login"

# ensure firebase (stops with helpful message if not configured)
try:
    init_firebase()
except Exception as e:
    st.error("Firebase initialization error: " + str(e))
    st.stop()

# show last upload time always
st.markdown(f"**Last Upload:** {load_upload_time()}")

# Guest screen
if st.session_state["mode"] == "guest":
    st.subheader("Guest Search")
    ok = download_latest_to_local()
    if not ok:
        st.warning("No file available. Ask Admin to upload.")
    else:
        # try reading
        try:
            df = pd.read_excel(LOCAL_DOWNLOAD, engine="openpyxl")
        except Exception:
            try:
                df = pd.read_csv(LOCAL_DOWNLOAD)
            except Exception:
                st.error("Failed to read latest file. Ask Admin to re-upload.")
                df = None
        if df is not None:
            q = st.text_input("", placeholder="Enter text to search")
            if st.button("SUBMIT"):
                res = df[df.apply(lambda row: row.astype(str).str.contains(str(q), case=False, na=False).any(), axis=1)]
                if res.empty:
                    st.warning("No matches found.")
                else:
                    st.success(f"{len(res)} rows found")
                    st.dataframe(res)

# Admin login
elif st.session_state["mode"] == "admin_login":
    st.subheader("Admin Login")
    user = st.text_input("ID")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == ADMIN_USER and pwd == ADMIN_PASS:
            st.session_state["mode"] = "admin_panel"
            st.rerun()
        else:
            st.error("Invalid credentials")

# Admin panel
elif st.session_state["mode"] == "admin_panel":
    st.subheader("Admin Panel")
    st.markdown(f"**Last Upload:** {load_upload_time()}")

    st.markdown("### Upload new version (old versions are kept)")
    uploaded = st.file_uploader("Upload Excel or CSV", type=["xlsx","csv"])
    if uploaded:
        b = uploaded.getvalue()
        created = upload_new_version(b, original_name=uploaded.name)
        st.success(f"Uploaded as: {created}")
        st.rerun()

    st.markdown("---")
    st.markdown("### Versions (newest first)")
    versions = list_versions()
    if not versions:
        st.info("No versions yet.")
    else:
        # show selectbox of versions (display name with time)
        sel = st.selectbox("Select version", options=[v["name"] for v in versions], format_func=lambda x: x)
        if st.button("Download & Preview Selected Version"):
            ok = download_specific_version(sel)
            if not ok:
                st.error("Failed to download selected version.")
            else:
                try:
                    dfv = pd.read_excel(LOCAL_DOWNLOAD, engine="openpyxl")
                except Exception:
                    try:
                        dfv = pd.read_csv(LOCAL_DOWNLOAD)
                    except Exception:
                        dfv = None
                if dfv is not None:
                    st.dataframe(dfv.head(100))

        if st.button("Delete Selected Version"):
            delete_version(sel)
            st.success(f"Deleted: {sel}")
            st.rerun()

    st.markdown("---")
    st.markdown("### Quick admin search on latest")
    if download_latest_to_local():
        try:
            df_latest = pd.read_excel(LOCAL_DOWNLOAD, engine="openpyxl")
        except Exception:
            try:
                df_latest = pd.read_csv(LOCAL_DOWNLOAD)
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

    if st.button("Logout Admin"):
        st.session_state["mode"] = "guest"
        st.rerun()

