import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Excel Search App", layout="wide")
st.title("Excel Search Application")

UPLOAD_PATH = "current.xlsx"

# ---------- File Upload ----------
uploaded_file = st.file_uploader("Upload Excel File (.xlsx or .csv)", type=["xlsx", "csv"])

if uploaded_file:
    # Remove old file if exists
    if os.path.exists(UPLOAD_PATH):
        os.remove(UPLOAD_PATH)
    # Save new file
    with open(UPLOAD_PATH, "wb") as f:
        f.write(uploaded_file.getbuffer())
    st.success("File uploaded and saved as current.xlsx")

# ---------- Search Section ----------
if os.path.exists(UPLOAD_PATH):
    try:
        # Try read excel, fallback to csv
        if UPLOAD_PATH.lower().endswith(".csv"):
            df = pd.read_csv(UPLOAD_PATH)
        else:
            df = pd.read_excel(UPLOAD_PATH, engine="openpyxl")
    except Exception as e:
        st.error(f"Failed to read the file: {e}")
        st.stop()

    st.write(f"**Loaded file:** {UPLOAD_PATH} — {df.shape[0]} rows, {df.shape[1]} columns")
    query = st.text_input("Search for text or number (case-insensitive)")

    cols_to_show = st.multiselect("Columns to display in results (leave empty = all)", options=list(df.columns))

    if query:
        # Convert all cells to strings and check if query present (case-insensitive)
        mask = df.apply(lambda row: row.astype(str).str.contains(str(query), case=False, na=False).any(), axis=1)
        result = df[mask]
        if not result.empty:
            st.write("### Results Found:")
            if cols_to_show:
                st.dataframe(result[cols_to_show])
            else:
                st.dataframe(result)
        else:
            st.warning("No matching results found.")
else:
    st.info("Upload a file (Excel .xlsx or .csv) to start searching.")
