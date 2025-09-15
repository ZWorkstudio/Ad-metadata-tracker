# Advanced Nielsen-Style Ad Metadata Tracker
# Simulates Database Management workflow: A detailing and AD Telecast - broadcast monitoring, metadata entry, QA, shift-based reporting

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime, time, timedelta
import io
import plotly.express as px
import plotly.graph_objects as go
from dateutil.parser import parse

# Optional fuzzy matching
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ = True
except:
    RAPIDFUZZ = False

# Set page config
st.set_page_config(page_title="Nielsen Ad Tracker", layout="wide", page_icon="📺")

# ---------------------- Helper Functions ----------------------
def create_unique_id():
    return str(uuid.uuid4())

def normalize_text(x):
    return str(x).strip().lower() if pd.notna(x) else ""

def parse_dates_safe(df, col="Air Time"):
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except:
            df[col] = df[col].apply(lambda x: parse(str(x)) if pd.notna(x) else pd.NaT)
    return df

def add_audit_fields(df, source_label="manual"):
    df = df.copy()
    if "ad_id" not in df.columns:
        df["ad_id"] = [create_unique_id() for _ in range(len(df))]
    if "ingested_at" not in df.columns:
        df["ingested_at"] = datetime.utcnow()
    df["source"] = source_label
    return df

def detect_duplicates(df, subset_keys=["Advertiser","Brand","Channel","Duration","Air Time"], fuzzy_threshold=0.9):
    df = df.copy()
    for k in subset_keys:
        if k not in df.columns:
            df[k] = ""
    df["_key"] = df.apply(lambda r: "|".join([normalize_text(r[k]) for k in subset_keys]), axis=1)
    
    exact_dup = df.duplicated(subset=["_key"], keep=False)
    fuzzy_dup = pd.Series([False]*len(df), index=df.index)
    
    if RAPIDFUZZ:
        keys = df["_key"].tolist()
        for i, key in enumerate(keys):
            for j in range(i+1, len(keys)):
                score = fuzz.ratio(key, keys[j])/100
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
    return exact_dup | fuzzy_dup

def export_df_to_excel_bytes(cleaned, duplicates, summary):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        cleaned.to_excel(writer, index=False, sheet_name="Cleaned")
        duplicates.to_excel(writer, index=False, sheet_name="Duplicates")
        summary.to_excel(writer, index=False, sheet_name="Shift Report")
    return buffer.getvalue()

def generate_creative_description(row):
    return f"{row['Brand']} - {row['Product']} aired on {row['Channel']} for {row['Duration']} seconds."

def current_shift():
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    if time(0,0) <= now_ist.time() <= time(9,0):
        return "12am-9am IST"
    return "Outside shift"

# ---------------------- Streamlit UI ----------------------
st.markdown("""
<style>
.kpi-card {background: linear-gradient(90deg,#00c6ff,#0072ff); color:white; padding:20px; border-radius:15px; text-align:center;}
.header {font-size:36px; font-weight:bold; color:#0072ff; text-align:center;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header">📺 Nielsen Ad Metadata Tracker</div>', unsafe_allow_html=True)
st.write("Simulates monitoring, coding, and reporting of broadcast ads exactly like Nielsen workflow.")

# Sidebar controls
with st.sidebar:
    st.header("Data Ingestion")
    ingestion_mode = st.radio("Select mode", ("Upload Station Logs","Manual Entry","Load Example Logs"))
    fuzzy_threshold = st.slider("Deduplication Threshold (%)", 70, 100, 90)
    source_label = st.text_input("Source Label", "demo_station")
    st.markdown("---")
    st.header("Export Options")
    st.write("Download cleaned dataset and reports")

# Session state
if "ads_df" not in st.session_state: st.session_state.ads_df = pd.DataFrame()
if "audit_log" not in st.session_state: st.session_state.audit_log = []

# Data ingestion
if ingestion_mode=="Upload Station Logs":
    uploaded_file = st.file_uploader("Upload CSV/Excel", type=["csv","xlsx"])
    if uploaded_file:
        try:
            df_new = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
            df_new = parse_dates_safe(df_new, "Air Time")
            df_new["Creative Description"] = df_new.apply(generate_creative_description, axis=1)
            df_new = add_audit_fields(df_new, source_label)
            st.session_state.ads_df = pd.concat([st.session_state.ads_df, df_new], ignore_index=True)
            st.success(f"Loaded {len(df_new)} records from {uploaded_file.name}")
            st.session_state.audit_log.append((datetime.utcnow(), f"Uploaded {uploaded_file.name}"))
        except Exception as e:
            st.error(f"Failed: {e}")
elif ingestion_mode=="Manual Entry":
    with st.form("manual_entry_form"):
        cols = st.columns(3)
        advertiser = cols[0].text_input("Advertiser")
        brand = cols[1].text_input("Brand")
        product = cols[2].text_input("Product")
        cols2 = st.columns(3)
        channel = cols2[0].selectbox("Channel", ["TV","Digital","OOH","Radio","Print","Social","Other"])
        duration = cols2[1].number_input("Duration (seconds)", min_value=1, step=1)
        air_time = cols2[2].time_input("Air Time", value=datetime.now().time())
        submit = st.form_submit_button("Add Ad")
        if submit:
            new = pd.DataFrame([{"Advertiser":advertiser,"Brand":brand,"Product":product,"Channel":channel,"Duration":duration,"Air Time":datetime.combine(datetime.today(),air_time)}])
            new["Creative Description"] = new.apply(generate_creative_description, axis=1)
            new = add_audit_fields(new, source_label)
            st.session_state.ads_df = pd.concat([st.session_state.ads_df,new], ignore_index=True)
            st.success("Ad added")
            st.session_state.audit_log.append((datetime.utcnow(), f"Manual entry: {brand}/{advertiser}"))
else:
    if st.button("Load Example Logs"):
        df_example = pd.DataFrame([
            {"Advertiser":"PepsiCo","Brand":"Pepsi","Product":"Soda","Channel":"TV","Duration":30,"Air Time":datetime(2025,8,15,1,0)},
            {"Advertiser":"Coca-Cola","Brand":"Coca-Cola","Product":"Drink","Channel":"Digital","Duration":15,"Air Time":datetime(2025,8,15,2,30)},
            {"Advertiser":"Nike","Brand":"Nike","Product":"Shoes","Channel":"OOH","Duration":10,"Air Time":datetime(2025,8,15,3,45)}
        ])
        df_example["Creative Description"] = df_example.apply(generate_creative_description, axis=1)
        df_example = add_audit_fields(df_example, source_label)
        st.session_state.ads_df = pd.concat([st.session_state.ads_df, df_example], ignore_index=True)
        st.success("Example logs loaded")
        st.session_state.audit_log.append((datetime.utcnow(), "Loaded example logs"))

# ---------------------- Deduplication & Cleaning ----------------------
if st.button("Run Deduplication & QA"):
    df = st.session_state.ads_df.copy()
    dup_mask = detect_duplicates(df, fuzzy_threshold=fuzzy_threshold/100)
    df["Duplicate"] = dup_mask
    df["Keep"] = ~dup_mask
    cleaned = df[df["Keep"]].copy().reset_index(drop=True)
    duplicates = df[df["Duplicate"]].copy().reset_index(drop=True)
    summary = pd.DataFrame([{"Metric":"Total Ads","Value":len(df)},
                            {"Metric":"Duplicates","Value":dup_mask.sum()},
                            {"Metric":"Processed This Shift","Value":len(cleaned)},
                            {"Metric":"Current Shift","Value":current_shift()}])
    st.session_state.cleaned_df = cleaned
    st.session_state.duplicates_df = duplicates
    st.session_state.summary_df = summary
    st.session_state.ads_df = df
    st.success("Deduplication & QA complete")
    st.session_state.audit_log.append((datetime.utcnow(), f"Deduplication run threshold={fuzzy_threshold}%"))

# ---------------------- Nielsen-Style Dashboard ----------------------
st.markdown("---")
st.header("📊 Dashboard & Shift Report")

if "ads_df" in st.session_state and not st.session_state.ads_df.empty:
    df = st.session_state.ads_df.copy()
    cleaned = st.session_state.get("cleaned_df", df)
    duplicates = st.session_state.get("duplicates_df", pd.DataFrame())
    
    # KPI cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Ads", len(df))
    kpi2.metric("Processed This Shift", len(cleaned))
    kpi3.metric("Duplicates", len(duplicates))
    kpi4.metric("Current Shift", current_shift())
    
    # Charts
    ch1, ch2 = st.columns([2,1])
    with ch1:
        by_channel = df.groupby("Channel")["ad_id"].count().reset_index().rename(columns={"ad_id":"Count"})
        fig1 = px.bar(by_channel, x="Channel", y="Count", title="Ads by Channel", color="Count")
        st.plotly_chart(fig1)
        
        by_brand = df.groupby("Brand")["ad_id"].count().reset_index().rename(columns={"ad_id":"Count"})
        fig2 = px.pie(by_brand, names="Brand", values="Count", title="Ads by Brand")
        st.plotly_chart(fig2)
    
    with ch2:
        # Shift timeline
        df["Hour"] = df["Air Time"].dt.hour
        shift_count = df.groupby("Hour")["ad_id"].count().reset_index()
        fig3 = px.line(shift_count, x="Hour", y="ad_id", title="Ads Processed per Hour", markers=True)
        st.plotly_chart(fig3)
    
    # Show tables
    st.subheader("Cleaned Ads")
    st.dataframe(cleaned)
    st.subheader("Duplicates / QA Flagged")
    st.dataframe(duplicates)
    
    # Export
    st.download_button("Download Full Shift Report (Excel)", 
                       export_df_to_excel_bytes(cleaned, duplicates, summary),
                       file_name="nielsen_shift_report.xlsx")

# ---------------------- Audit Log ----------------------
st.markdown("---")
st.subheader("📜 Audit Log")
if st.session_state.audit_log:
    st.table(pd.DataFrame(st.session_state.audit_log, columns=["Timestamp UTC","Action"]))
else:
    st.write("No actions yet.")
