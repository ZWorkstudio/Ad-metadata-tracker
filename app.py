# Ad Metadata Tracker - Advanced Recruiter-Ready Version
# Features: Manual entry, CSV upload, dedup, traceability, dashboard, circle charts, PDF & Excel export

import streamlit as st
import pandas as pd
import uuid
from datetime import datetime
import io
import plotly.express as px
import matplotlib.pyplot as plt
import difflib
from dateutil.parser import parse

# Optional packages
HAS_CIRCLE = False
HAS_PDF = False
try:
    import pycirclify
    HAS_CIRCLE = True
except ImportError:
    pass

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    HAS_PDF = True
except ImportError:
    pass

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

def export_pdf_report(cleaned, duplicates):
    if not HAS_PDF:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph("Ad Metadata Tracker - Report", styles['Title']))
    elements.append(Spacer(1,12))
    # Cleaned Ads
    if not cleaned.empty:
        data = [cleaned.columns.tolist()] + cleaned.head(10).values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.black)]))
        elements.append(Paragraph("Cleaned Ads (Sample):", styles['Heading2']))
        elements.append(table)
        elements.append(Spacer(1,12))
    # Duplicates
    if not duplicates.empty:
        data = [duplicates.columns.tolist()] + duplicates.head(5).values.tolist()
        table = Table(data)
        table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.5,colors.red)]))
        elements.append(Paragraph("Duplicates (Sample):", styles['Heading2']))
        elements.append(table)
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

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

# ---------------------- Column Handling ----------------------
required_cols = ["advertiser","brand","channel","format","date","spend"]
for col in required_cols:
    if col not in df.columns:
        st.warning(f"Column '{col}' missing. Auto-creating placeholder.")
        df[col] = "" if col != "spend" else 0

for col in required_cols:
    if col != "date":
        df[col] = df[col].astype(str).str.strip().str.title()
df = parse_dates_safe(df, "date")
df = add_audit_fields(df, source_label="uploaded" if uploaded_file else "example")

# ---------------------- Deduplication ----------------------
df["is_duplicate"] = detect_duplicates(df, subset_keys=required_cols[:-1])  # exclude spend

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
st.metric("Total Spend", cleaned["spend"].sum())

# Bar chart
fig_bar = px.bar(cleaned, x="brand", y="spend", color="channel", title="Ad Spend by Brand & Channel")
st.plotly_chart(fig_bar, use_container_width=True)

# Circle Packing Chart
st.subheader("Circle Packing: Brands & Products")
if HAS_CIRCLE and not cleaned.empty:
    grp = cleaned.groupby("brand")["format"].count().reset_index().rename(columns={"format":"count"})
    circles = pycirclify.circlify(grp["count"].tolist(), show_enclosure=False, target_enclosure=pycirclify.Circle(x=0,y=0,r=1))
    fig, ax = plt.subplots(figsize=(6,6))
    ax.axis("off")
    for circle, (_, row) in zip(circles, grp.iterrows()):
        x, y, r = circle
        ax.add_patch(plt.Circle((x,y),r,alpha=0.5,linewidth=2))
        ax.text(x, y, row["brand"], ha="center", va="center", fontsize=10)
    st.pyplot(fig)
elif not HAS_CIRCLE:
    st.info("Circle Packing Chart not available (pycirclify not installed)")

# ---------------------- Export ----------------------
excel_bytes = export_df_to_excel_bytes(cleaned)
st.download_button("Download Cleaned Ads as Excel", excel_bytes, file_name="cleaned_ads.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if HAS_PDF:
    pdf_bytes = export_pdf_report(cleaned, dupes)
    st.download_button("Download PDF Report", pdf_bytes, file_name="ad_metadata_report.pdf", mime="application/pdf")
else:
    st.info("PDF export not available (reportlab not installed)")

# ---------------------- Role Simulation ----------------------
st.header("Role Simulation: Manual Entry")
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
