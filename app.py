# Ad Metadata Tracker - Advanced Streamlit App
# Upgraded version: Pro polished dashboard with animations, fuzzy deduplication, KPI cards, heatmaps, trend lines, multi-sheet Excel export, and audit trail

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import io
import plotly.express as px
import plotly.graph_objects as go
from dateutil.parser import parse

# Optional robust fuzzy matcher
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ = True
except Exception:
    RAPIDFUZZ = False

st.set_page_config(page_title="Advanced Ad Metadata Tracker", layout="wide", page_icon="📊")

# ---------------------- Helper functions ----------------------

def create_unique_id():
    return str(uuid.uuid4())

def normalize_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower()

# Load example dataset
def load_example_data():
    data = [
        {"advertiser": "PepsiCo", "brand": "Pepsi", "channel": "TV", "format": "30s", "date": "2025-08-15", "spend": 250000},
        {"advertiser": "PepsiCo", "brand": "Pepsi", "channel": "Digital", "format": "15s", "date": "2025-08-20", "spend": 120000},
        {"advertiser": "Coca-Cola", "brand": "Coca-Cola", "channel": "TV", "format": "30s", "date": "2025-08-09", "spend": 300000},
        {"advertiser": "Nike Inc.", "brand": "Nike", "channel": "OOH", "format": "Poster", "date": "2025-07-30", "spend": 50000},
    ]
    df = pd.DataFrame(data)
    df["ad_id"] = [create_unique_id() for _ in range(len(df))]
    df["ingested_at"] = datetime.utcnow()
    return df

# Parse dates safely
def parse_dates_safe(df, col="date"):
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col]).dt.date
        except Exception:
            df[col] = df[col].apply(lambda x: parse(str(x)).date() if pd.notna(x) else pd.NaT)
    return df

# Deduplication
def detect_duplicates(df, subset_keys=["advertiser","brand","channel","format","date"], fuzzy_threshold=0.92):
    df = df.copy()
    for k in subset_keys:
        if k not in df.columns:
            df[k] = ""
    df["_key"] = df.apply(lambda r: "|".join([normalize_text(r[k]) for k in subset_keys]), axis=1)

    exact_dup = df.duplicated(subset=["_key"], keep=False)
    fuzzy_dup = pd.Series([False]*len(df), index=df.index)

    if RAPIDFUZZ:
        from rapidfuzz import fuzz
        keys = df["_key"].tolist()
        for i, key in enumerate(keys):
            for j in range(i+1, len(keys)):
                score = fuzz.ratio(key, keys[j]) / 100.0
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True
    else:
        import difflib
        keys = df["_key"].tolist()
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                score = difflib.SequenceMatcher(None, keys[i], keys[j]).ratio()
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True

    combined = exact_dup | fuzzy_dup
    return combined

# Audit fields
def add_audit_fields(df, source_label="manual"):
    df = df.copy()
    if "ad_id" not in df.columns:
        df["ad_id"] = [create_unique_id() for _ in range(len(df))]
    if "ingested_at" not in df.columns:
        df["ingested_at"] = datetime.utcnow()
    df["source"] = source_label
    return df

# Export Excel with multiple sheets
def export_df_to_excel_bytes(cleaned, duplicates, summary):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        cleaned.to_excel(writer, index=False, sheet_name="Cleaned")
        duplicates.to_excel(writer, index=False, sheet_name="Duplicates")
        summary.to_excel(writer, index=False, sheet_name="Summary")
    return buffer.getvalue()

# ---------------------- Streamlit UI ----------------------

# Header with animation
st.markdown("""
<style>
.header-anim {
  font-size:36px;
  font-weight:800;
  background: linear-gradient(90deg,#00c6ff,#0072ff,#00c6ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: slidebg 3s linear infinite;
}
@keyframes slidebg {0% {background-position: 0%} 100% {background-position: 200%}}
</style>
""", unsafe_allow_html=True)
st.markdown('<div class="header-anim">🚀 Advanced Ad Metadata Tracker</div>', unsafe_allow_html=True)
st.write("JD-aligned project: Clean, traceable ads dataset with dashboard, deduplication, and advanced reporting.")
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("Data Ingestion")
    ingestion_mode = st.radio("Select ingestion mode", ("Upload CSV/Excel","Manual entry","Load example dataset"))
    fuzzy_threshold = st.slider("Deduplication fuzzy threshold", 70, 100, 90)
    source_label = st.text_input("Source label", "replit_demo")
    st.markdown("---")
    st.header("Export Options")
    st.write("Download cleaned dataset and reports")

# Session state
if "ads_df" not in st.session_state:
    st.session_state.ads_df = pd.DataFrame()
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

# Data ingestion logic (Upload / Manual / Example)
if ingestion_mode == "Upload CSV/Excel":
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv","xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_new = pd.read_csv(uploaded_file)
            else:
                df_new = pd.read_excel(uploaded_file)
            df_new = parse_dates_safe(df_new)
            df_new = add_audit_fields(df_new, source_label=source_label)
            st.session_state.ads_df = pd.concat([st.session_state.ads_df, df_new], ignore_index=True)
            st.success(f"Loaded {len(df_new)} records from {uploaded_file.name}")
            st.session_state.audit_log.append((datetime.utcnow(), f"Uploaded {uploaded_file.name} ({len(df_new)} rows)"))
        except Exception as e:
            st.error(f"Failed to read file: {e}")

elif ingestion_mode == "Manual entry":
    with st.form("manual_entry_form"):
        cols = st.columns(3)
        advertiser = cols[0].text_input("Advertiser")
        brand = cols[1].text_input("Brand")
        channel = cols[2].selectbox("Channel", ["TV","Digital","OOH","Radio","Print","Social","Other"])
        cols2 = st.columns(3)
        format_ = cols2[0].text_input("Format")
        date_ = cols2[1].date_input("Date", value=datetime.today())
        spend = cols2[2].number_input("Spend", min_value=0.0, step=100.0)
        submit = st.form_submit_button("Add ad")
        if submit:
            new = pd.DataFrame([{"advertiser": advertiser, "brand": brand, "channel": channel, "format": format_, "date": date_, "spend": spend}])
            new = add_audit_fields(new, source_label=source_label)
            st.session_state.ads_df = pd.concat([st.session_state.ads_df, new], ignore_index=True)
            st.success("Ad added")
            st.session_state.audit_log.append((datetime.utcnow(), f"Manual entry: {brand} / {advertiser}"))

else: # example dataset
    if st.button("Load example dataset"):
        st.session_state.ads_df = pd.concat([st.session_state.ads_df, load_example_data()], ignore_index=True)
        st.success("Example dataset loaded")
        st.session_state.audit_log.append((datetime.utcnow(), "Loaded example dataset"))

# Data processing
if st.button("Run deduplication & clean"):
    with st.spinner("Processing..."):
        df = st.session_state.ads_df.copy()
        df = parse_dates_safe(df)
        dup_mask = detect_duplicates(df, fuzzy_threshold=(fuzzy_threshold/100.0))
        df["is_duplicate"] = dup_mask
        df["keep"] = ~df["is_duplicate"]
        cleaned = df[~df["is_duplicate"]].copy().reset_index(drop=True)
        duplicates = df[df["is_duplicate"]].copy().reset_index(drop=True)
        summary = pd.DataFrame([{"Metric": "Total Ads", "Value": len(df)},
                                {"Metric": "Duplicates", "Value": dup_mask.sum()},
                                {"Metric": "Total Spend", "Value": df['spend'].sum()}])
        st.session_state.cleaned_df = cleaned
        st.session_state.duplicates_df = duplicates
        st.session_state.summary_df = summary
        st.session_state.ads_df = df
        st.success("Deduplication complete")
        st.session_state.audit_log.append((datetime.utcnow(), f"Deduplication run (threshold={fuzzy_threshold}%)"))

# Dashboard
st.markdown("---")
st.header("Advanced Dashboard")
if "ads_df" in st.session_state and not st.session_state.ads_df.empty:
    df = st.session_state.ads_df.copy()
    cleaned = st.session_state.get("cleaned_df", df)
    duplicates = st.session_state.get("duplicates_df", pd.DataFrame())

    # KPI cards
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    kpi_col1.metric("Total Ads", len(df))
    kpi_col2.metric("Total Spend", f"{df['spend'].sum():,.0f}")
    kpi_col3.metric("Duplicates", len(df[df['is_duplicate']]))

    # Charts
    ch1, ch2 = st.columns([2,1])
    with ch1:
        if "channel" in df.columns:
            ch = df.groupby("channel")["ad_id"].count().reset_index().rename(columns={"ad_id":"count"})
            fig = px.bar(ch, x="channel", y="count", title="Ads by Channel")
            st.plotly_chart

