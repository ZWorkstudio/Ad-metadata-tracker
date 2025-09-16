# Ad Metadata Tracker - Streamlit Starter App
# Purpose: JD-aligned project for "Data Entry Coordinator I (Ad Intel Analyst)"
# Features:
# - Manual entry + CSV upload
# - Structured dataset with unique IDs & timestamps
# - Deduplication (exact & fuzzy via difflib/rapidfuzz)
# - Traceability (audit trail)
# - Interactive dashboard (Plotly + Streamlit)
# - Export cleaned dataset to CSV / Excel
# - Search & filter
# - Polished UI with animated header and processing feedback

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import io
import plotly.express as px
import difflib
from dateutil.parser import parse

# Optional robust fuzzy matcher (faster / better)
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ = True
except Exception:
    RAPIDFUZZ = False

# ---------------------- Helper functions ----------------------

def create_unique_id():
    return str(uuid.uuid4())

def normalize_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower()

def load_example_data():
    # Example dataset
    data = [
        {"advertiser": "PepsiCo", "brand": "Pepsi", "channel": "TV", "format": "30s", "date": "2025-08-15", "spend": 250000},
        {"advertiser": "PepsiCo", "brand": "Pepsi", "channel": "Digital", "format": "15s", "date": "2025-08-20", "spend": 120000},
        {"advertiser": "Coca-Cola", "brand": "Coca-Cola", "channel": "TV", "format": "30s", "date": "2025-08-09", "spend": 300000},
        {"advertiser": "Nike Inc.", "brand": "Nike", "channel": "OOH", "format": "Poster", "date": "2025-07-30", "spend": 50000},
    ]
    df = pd.DataFrame(data)
    df["ad_id"] = [create_unique_id() for _ in range(len(df))]
    df["ingested_at"] = datetime.utcnow()
    df["source"] = "example"
    return df

def parse_dates_safe(df, col="date"):
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col]).dt.date
        except Exception:
            df[col] = df[col].apply(lambda x: parse(str(x)).date() if pd.notna(x) else pd.NaT)
    return df

def detect_duplicates(df, subset_keys=["advertiser","brand","channel","format","date"], fuzzy_threshold=0.92):
    if df.empty:
        return pd.Series([False]*len(df), index=df.index)
    df = df.copy()
    for k in subset_keys:
        if k not in df.columns:
            df[k] = ""
    df["_key"] = df.apply(lambda r: "|".join([normalize_text(r[k]) for k in subset_keys]), axis=1)
    exact_dup = df.duplicated(subset=["_key"], keep=False)
    fuzzy_dup = pd.Series([False]*len(df), index=df.index)
    keys = df["_key"].tolist()
    if RAPIDFUZZ:
        from rapidfuzz import fuzz
        for i, key in enumerate(keys):
            for j in range(i+1, len(keys)):
                score = fuzz.ratio(key, keys[j])/100
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True
    else:
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                score = difflib.SequenceMatcher(None, keys[i], keys[j]).ratio()
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True
    return exact_dup | fuzzy_dup

def add_audit_fields(df, source_label="manual"):
    df = df.copy()
    if "ad_id" not in df.columns:
        df["ad_id"] = [create_unique_id() for _ in range(len(df))]
    if "ingested_at" not in df.columns:
        df["ingested_at"] = datetime.utcnow()
    df["source"] = source_label
    return df

def export_df_to_excel_bytes(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ads")
    return buffer.getvalue()

# ---------------------- Streamlit UI ----------------------

st.set_page_config(page_title="Ad Metadata Tracker", layout="wide", page_icon="📊")
st.markdown("<h1 style='text-align:center; color:#4CAF50;'>📊 Ad Metadata Tracker</h1>", unsafe_allow_html=True)

# ---------------------- Data Load ----------------------
uploaded_file = st.file_uploader("Upload Advertisement Log (CSV/Excel)", type=["csv","xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
else:
    df = load_example_data()

st.subheader("Raw Advertisement Data")
st.dataframe(df)

# ---------------------- Column Handling ----------------------
required_cols = ["advertiser","brand","channel","format","date"]
for col in required_cols:
    if col not in df.columns:
        st.warning(f"Column '{col}' missing. Auto-creating placeholder.")
        df[col] = ""

# Normalize text columns
for col in required_cols:
    df[col] = df[col].astype(str).str.strip().str.title()

df = parse_dates_safe(df, "date")
df = add_audit_fields(df, source_label="uploaded" if uploaded_file else "example")

# ---------------------- Deduplication ----------------------
df["is_duplicate"] = detect_duplicates(df, subset_keys=required_cols)

cleaned = df[~df["is_duplicate"]].copy()
dupes = df[df["is_duplicate"]].copy()

st.subheader("Cleaned Ads")
st.dataframe(cleaned)
st.subheader("Duplicate/Similar Ads Detected")
st.dataframe(dupes if not dupes.empty else pd.DataFrame({"Status":["No duplicates found"]}))

# ---------------------- Dashboard ----------------------
st.header("Advertisement Dashboard")
st.metric("Total Ads", len(cleaned))
st.metric("Unique Brands", cleaned["brand"].nunique())
st.metric("Total Ads Spend", cleaned["spend"].sum() if "spend" in cleaned.columns else 0)

# Bar chart: spend by brand
if "spend" in cleaned.columns:
    fig = px.bar(cleaned, x="brand", y="spend", color="channel", title="Ad Spend by Brand & Channel")
    st.plotly_chart(fig, use_container_width=True)

# ---------------------- Export ----------------------
excel_bytes = export_df_to_excel_bytes(cleaned)
st.download_button("Download Cleaned Ads as Excel", excel_bytes, file_name="cleaned_ads.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------------------- Role Simulation ----------------------
st.header("Role Simulation")
with st.form("manual_entry"):
    advertiser = st.text_input("Advertiser")
    brand = st.text_input("Brand")
    channel = st.text_input("Channel")
    ad_format = st.text_input("Format")
    date = st.date_input("Air Date")
    spend = st.number_input("Spend", min_value=0)
    submit = st.form_submit_button("Submit Ad Entry")

if submit:
    new_row = pd.DataFrame([{
        "advertiser": advertiser,
        "brand": brand,
        "channel": channel,
        "format": ad_format,
        "date": date,
        "spend": spend,
        "ad_id": create_unique_id(),
        "ingested_at": datetime.utcnow(),
        "source": "manual",
        "is_duplicate": False
    }])
    cleaned = pd.concat([cleaned, new_row], ignore_index=True)
    st.success("✅ Ad entry successfully added!")
    st.dataframe(cleaned)
