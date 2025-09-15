# Ad Metadata Tracker - Streamlit Starter App
# File: app.py
# Purpose: JD-aligned project for "Data Entry Coordinator I (Ad Intel Analyst)"
# Features:
# - Manual entry + CSV upload
# - Structured dataset with unique IDs & timestamps
# - Deduplication (exact & fuzzy via difflib)
# - Traceability (audit trail)
# - Interactive dashboard (Plotly + Streamlit)
# - Export cleaned dataset to CSV / Excel
# - Search & filter
# - Polished UI with animated header and processing feedback

# Dependencies:
# pip install streamlit pandas plotly openpyxl python-dateutil
# (Optional but recommended for better fuzzy matching: pip install rapidfuzz)

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import io
import plotly.express as px
import plotly.graph_objects as go
from dateutil.parser import parse
import difflib

# Optional robust fuzzy matcher (faster / better) if available
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
    # Small example dataset to showcase functionality
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


def parse_dates_safe(df, col="date"):
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col]).dt.date
        except Exception:
            # attempt parsing individually
            df[col] = df[col].apply(lambda x: parse(str(x)).date() if pd.notna(x) else pd.NaT)
    return df


def detect_duplicates(df, subset_keys=["advertiser","brand","channel","format","date"], fuzzy_threshold=0.92):
    """
    Returns a boolean Series marking duplicates.
    Strategy:
    - Create a composite key of normalized text for exact dup detection.
    - For fuzzy detection: compare pairs within same date or same advertiser to catch near-duplicates.
    """
    if df.empty:
        return pd.Series([], dtype=bool)

    df = df.copy()
    for k in subset_keys:
        if k not in df.columns:
            df[k] = ""
    df["_key"] = df.apply(lambda r: "|".join([normalize_text(r[k]) for k in subset_keys]), axis=1)

    # exact duplicates
    exact_dup = df.duplicated(subset=["_key"], keep=False)

    # fuzzy duplicates
    fuzzy_dup = pd.Series([False]*len(df), index=df.index)

    if RAPIDFUZZ:
        # use rapidfuzz for pairwise similarities (faster)
        from rapidfuzz import process
        keys = df["_key"].tolist()
        for i, key in enumerate(keys):
            # compare to later keys only for efficiency
            for j in range(i+1, len(keys)):
                score = fuzz.ratio(key, keys[j]) / 100.0
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True
    else:
        # difflib SequenceMatcher approach (slower but builtin)
        keys = df["_key"].tolist()
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                score = difflib.SequenceMatcher(None, keys[i], keys[j]).ratio()
                if score >= fuzzy_threshold:
                    fuzzy_dup.iat[i] = True
                    fuzzy_dup.iat[j] = True

    combined = exact_dup | fuzzy_dup
    return combined


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

# Animated header using CSS + simple emoji animation
st.markdown("""
<style>
.header-anim {
  font-size:32px;
  font-weight:800;
  background: linear-gradient(90deg,#00c6ff,#0072ff,#00c6ff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: slidebg 3s linear infinite;
}
@keyframes slidebg {
  0% {background-position: 0%}
  100% {background-position: 200%}
}
.small-muted { color: #6c757d; font-size:14px }
</style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([3,1])
with col1:
    st.markdown('<div class="header-anim">Ad Metadata Tracker — Clean, Traceable, Reportable</div>', unsafe_allow_html=True)
    st.write("""A JD-aligned project for Data Entry Coordinator / Ad Intel Analyst roles — upload ads, clean & dedupe records, track traceability, and create internal reports.""")
with col2:
    st.image("https://static.streamlit.io/examples/dice.jpg", width=120)

st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("Ingest Data")
    ingestion_mode = st.radio("How would you like to add ad data?", ("Upload CSV/Excel","Manual entry","Load example dataset"))
    fuzzy_threshold = st.slider("Duplicate fuzzy threshold", 70, 100, 90)
    source_label = st.text_input("Source label (for traceability)", "replit_demo")
    st.markdown("---")
    st.header("Export / Save")
    st.write("Download the cleaned dataset for internal reporting")

# Session state for dataset persistence across interactions
if "ads_df" not in st.session_state:
    st.session_state.ads_df = pd.DataFrame()
if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

# Data ingestion
if ingestion_mode == "Upload CSV/Excel":
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv","xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.type == "text/csv" or uploaded_file.name.endswith('.csv'):
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
    with st.form(key="manual_entry_form"):
        cols = st.columns(3)
        advertiser = cols[0].text_input("Advertiser")
        brand = cols[1].text_input("Brand")
        channel = cols[2].selectbox("Channel", ["TV","Digital","OOH","Radio","Print","Social","Other"]) 
        cols2 = st.columns(3)
        format_ = cols2[0].text_input("Format (eg 30s, 15s, Poster)")
        date_ = cols2[1].date_input("Ad Date", value=datetime.today())
        spend = cols2[2].number_input("Spend (in local currency)", min_value=0.0, step=100.0)
        submit = st.form_submit_button("Add ad")
        if submit:
            new = pd.DataFrame([{"advertiser": advertiser, "brand": brand, "channel": channel, "format": format_, "date": date_, "spend": spend}])
            new = add_audit_fields(new, source_label=source_label)
            st.session_state.ads_df = pd.concat([st.session_state.ads_df, new], ignore_index=True)
            st.success("Ad added to dataset")
            st.session_state.audit_log.append((datetime.utcnow(), f"Manual entry: {brand} / {advertiser}"))

else: # example
    if st.button("Load example dataset"):
        st.session_state.ads_df = pd.concat([st.session_state.ads_df, load_example_data()], ignore_index=True)
        st.success("Example dataset loaded")
        st.session_state.audit_log.append((datetime.utcnow(), "Loaded example dataset"))

# Processing controls
st.markdown("---")
process_col1, process_col2 = st.columns([3,1])
with process_col1:
    st.subheader("Data Cleaning & Deduplication")
    if st.button("Run deduplication & clean"):
        with st.spinner("Processing dataset — deduping & cleaning..."):
            df = st.session_state.ads_df.copy()
            df = parse_dates_safe(df)
            # Basic normalization
            for c in ["advertiser","brand","channel","format"]:
                if c in df.columns:
                    df[c] = df[c].astype(str)
                else:
                    df[c] = ""
            # detect duplicates
            dup_mask = detect_duplicates(df, fuzzy_threshold=(fuzzy_threshold/100.0))
            df["is_duplicate"] = dup_mask
            # if duplicates exist, mark keep policy
            df["keep"] = ~df["is_duplicate"]

            # create a cleaned df view = non-duplicates or first occurrence
            cleaned = df[~df["is_duplicate"]].copy()
            cleaned.reset_index(drop=True, inplace=True)
            st.session_state.cleaned_df = cleaned
            st.session_state.ads_df = df
            st.success("Deduplication complete")
            st.session_state.audit_log.append((datetime.utcnow(), f"Deduplication run (threshold={fuzzy_threshold}%)"))

with process_col2:
    st.subheader("Quick stats")
    df_preview = st.session_state.ads_df
    st.metric("Total records", len(df_preview))
    dup_count = int(df_preview["is_duplicate"].sum()) if "is_duplicate" in df_preview.columns else 0
    st.metric("Detected duplicates", dup_count)

# Dashboard
st.markdown("---")
st.header("Reporting Dashboard")

if "ads_df" in st.session_state and not st.session_state.ads_df.empty:
    df = st.session_state.ads_df.copy()
    df = parse_dates_safe(df)
    # Provide a cleaned view if available
    cleaned = st.session_state.get("cleaned_df", df[~df.get("is_duplicate", pd.Series([False]*len(df)))])

    # Filters
    with st.expander("Filters & Search", expanded=False):
        f_col1, f_col2, f_col3 = st.columns(3)
        advertiser_filter = f_col1.text_input("Advertiser contains")
        brand_filter = f_col2.text_input("Brand contains")
        channel_filter = f_col3.multiselect("Channel", options=sorted(df["channel"].dropna().unique().tolist()))
        date_range = st.slider("Date range", min_value=pd.to_datetime(df["date"]).min().date() if not df["date"].isna().all() else datetime(2020,1,1).date(), max_value=pd.to_datetime(df["date"]).max().date() if not df["date"].isna().all() else datetime.today().date(), value=(pd.to_datetime(df["date"]).min().date() if not df["date"].isna().all() else datetime(2020,1,1).date(), pd.to_datetime(df["date"]).max().date() if not df["date"].isna().all() else datetime.today().date()))

        # apply filters
        mask = pd.Series([True]*len(df))
        if advertiser_filter:
            mask &= df["advertiser"].str.contains(advertiser_filter, case=False, na=False)
        if brand_filter:
            mask &= df["brand"].str.contains(brand_filter, case=False, na=False)
        if channel_filter:
            mask &= df["channel"].isin(channel_filter)
        if date_range:
            mask &= (pd.to_datetime(df["date"]).dt.date >= date_range[0]) & (pd.to_datetime(df["date"]).dt.date <= date_range[1])

        filtered = df[mask]
    
    st.subheader("Summary Metrics")
    colA, colB, colC, colD = st.columns(4)
    colA.metric("Total Ads", len(filtered))
    colB.metric("Unique Brands", filtered["brand"].nunique() if "brand" in filtered.columns else 0)
    colC.metric("Total Spend", f"{filtered['spend'].sum():,.0f}" if "spend" in filtered.columns else "0")
    dup_count = int(filtered["is_duplicate"].sum()) if "is_duplicate" in filtered.columns else 0
    colD.metric("Duplicates (in view)", dup_count)

    st.subheader("Visualizations")
    viz_col1, viz_col2 = st.columns([2,1])
    with viz_col1:
        # Ads by Channel
        if "channel" in filtered.columns and not filtered["channel"].isna().all():
            ch = filtered.groupby("channel")["ad_id"].count().reset_index().rename(columns={"ad_id":"count"})
            fig = px.bar(ch, x="channel", y="count", title="Ads by Channel", labels={"count":"# Ads"})
            st.plotly_chart(fig, use_container_width=True)

        # Spend over time
        if "date" in filtered.columns and "spend" in filtered.columns:
            ts = filtered.dropna(subset=["date"]).copy()
            ts["date"] = pd.to_datetime(ts["date"]).dt.date
            tsagg = ts.groupby("date")["spend"].sum().reset_index()
            fig2 = px.line(tsagg, x="date", y="spend", title="Spend Over Time", labels={"spend":"Total Spend"})
            st.plotly_chart(fig2, use_container_width=True)

    with viz_col2:
        st.markdown("### Top Brands by Spend")
        if "brand" in filtered.columns and "spend" in filtered.columns:
            top = filtered.groupby("brand")["spend"].sum().reset_index().sort_values("spend", ascending=False).head(10)
            st.table(top)

    st.subheader("Data Table & Traceability")
    show_table = st.checkbox("Show dataset table (paginated)", value=True)
    if show_table:
        display_df = filtered.copy()
        display_df = display_df[[c for c in ["ad_id","advertiser","brand","channel","format","date","spend","is_duplicate","keep","ingested_at","source"] if c in display_df.columns]]
        st.dataframe(display_df.reset_index(drop=True))

    # Export
    st.markdown("---")
    st.subheader("Export cleaned dataset")
    export_col1, export_col2 = st.columns([1,1])
    with export_col1:
        csv_bytes = filtered.to_csv(index=False).encode('utf-8')
        st.download_button(label="Download CSV", data=csv_bytes, file_name="ads_cleaned.csv", mime="text/csv")
    with export_col2:
        xlsx_bytes = export_df_to_excel_bytes(filtered)
        st.download_button(label="Download Excel", data=xlsx_bytes, file_name="ads_cleaned.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.info("No ad data yet — upload a CSV or add ads manually to get started.")

# Audit log viewer
st.markdown("---")
st.header("Audit Log & Traceability Notes")
if st.session_state.audit_log:
    log_df = pd.DataFrame([{"time": t, "action": a} for t,a in st.session_state.audit_log])
    st.table(log_df)
else:
    st.write("No actions recorded yet.")

# Footer / Next steps
st.markdown("---")
st.markdown("**Next steps (suggested for LinkedIn showcase):**\n\n"
            "1. Deploy this app on Replit and take a clean screenshot of the dashboard.\n"
            "2. Add a short README highlighting features that map to the job JD (traceability, deduplication, reporting).\n"
            "3. Share link + 1-2 screenshots on LinkedIn with a clear caption: e.g., 'Built an Ad Metadata Tracker to mirror Nielsen's Ad Intel workflows — clean, traceable datasets for internal reporting.'")

st.caption("Built with ❤️ for your Nielsen JD match — customize fields & visuals to match their exact schema.")
