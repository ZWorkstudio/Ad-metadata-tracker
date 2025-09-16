import streamlit as st
import pandas as pd
import plotly.express as px
import io
import datetime

# Optional packages (guarded)
try:
    import matplotlib.pyplot as plt
    import pycirclify
    HAS_CIRCLE = True
except ImportError:
    HAS_CIRCLE = False

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    HAS_PDF = True
except ImportError:
    HAS_PDF = False


# ------------------ Sample Fake Dataset ------------------
@st.cache_data
def load_data():
    data = {
        "Channel": ["Channel A", "Channel B", "Channel A", "Channel C", "Channel B"],
        "Ad Title": ["Summer Sale", "New Car Launch", "Summer Sale", "Tech Expo", "Fitness Promo"],
        "Brand": ["BrandX", "BrandY", "BrandX", "BrandZ", "BrandY"],
        "Product": ["Shoes", "Car", "Shoes", "Gadget", "Gym"],
        "Duration": [30, 45, 30, 60, 20],
        "Air Time": pd.date_range("2025-09-01", periods=5, freq="H"),
    }
    return pd.DataFrame(data)


# ------------------ Main App ------------------
st.set_page_config(page_title="AdVision Tracker", layout="wide")
st.title("📺 AdVision Tracker")
st.markdown("### A Metadata Tracking & Reporting Dashboard")

df = load_data()

# File Upload
uploaded_file = st.file_uploader("Upload Advertisement Log (CSV/Excel)", type=["csv", "xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

st.subheader("📊 Raw Advertisement Data")
st.dataframe(df)

# ------------------ Data Cleaning ------------------
st.header("🧹 Data Cleaning & Deduplication")
df["Ad Title"] = df["Ad Title"].str.strip().str.title()

from rapidfuzz import fuzz
def is_duplicate(row, seen):
    for s in seen:
        if fuzz.ratio(row["Ad Title"], s) > 90:
            return True
    return False

cleaned, dupes = [], []
seen = []
for _, row in df.iterrows():
    if is_duplicate(row, seen):
        dupes.append(row)
    else:
        cleaned.append(row)
        seen.append(row["Ad Title"])

cleaned = pd.DataFrame(cleaned)
dupes = pd.DataFrame(dupes)

col1, col2 = st.columns(2)
with col1:
    st.write("✅ Cleaned Ads")
    st.dataframe(cleaned)
with col2:
    st.write("⚠️ Duplicates Detected")
    st.dataframe(dupes if not dupes.empty else pd.DataFrame({"Status": ["No duplicates found"]}))

# ------------------ Dashboard & KPIs ------------------
st.header("📈 Advertisement Dashboard")

# KPIs
st.subheader("📌 Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("Total Ads", len(cleaned))
col2.metric("Unique Brands", cleaned["Brand"].nunique())
col3.metric("Total Air Time (mins)", cleaned["Duration"].sum())

# Bar Chart
fig1 = px.bar(cleaned, x="Brand", y="Duration", color="Product", title="Ad Duration by Brand")
st.plotly_chart(fig1, use_container_width=True)

# Pie Chart
fig2 = px.pie(cleaned, names="Channel", title="Ad Distribution by Channel")
st.plotly_chart(fig2, use_container_width=True)

# Time Series
fig3 = px.line(cleaned, x="Air Time", y="Duration", color="Brand", title="Ad Timeline")
st.plotly_chart(fig3, use_container_width=True)

# Circle Packing (if available)
st.subheader("🔵 Circle Packing: Brands & Products")
if HAS_CIRCLE and not cleaned.empty:
    brand_groups = (
        cleaned.groupby("Brand")["Product"]
        .count()
        .reset_index()
        .rename(columns={"Product": "Count"})
    )

    circles = pycirclify.circlify(
        brand_groups["Count"].tolist(),
        show_enclosure=False,
        target_enclosure=pycirclify.Circle(x=0, y=0, r=1),
    )

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.axis("off")
    for circle, (_, row) in zip(circles, brand_groups.iterrows()):
        x, y, r = circle
        ax.add_patch(plt.Circle((x, y), r, alpha=0.5, linewidth=2))
        ax.text(x, y, row["Brand"], ha="center", va="center", fontsize=10)
    st.pyplot(fig)
elif not HAS_CIRCLE:
    st.info("🔵 Circle chart not available (pycirclify not installed).")

# ------------------ Export Reports ------------------
st.header("📂 Export Reports")

# Excel Export
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    cleaned.to_excel(writer, index=False, sheet_name="Cleaned Ads")
    if not dupes.empty:
        dupes.to_excel(writer, index=False, sheet_name="Duplicates")
    summary = pd.DataFrame({
        "Metric": ["Total Ads", "Unique Brands", "Total Duration"],
        "Value": [len(cleaned), cleaned['Brand'].nunique(), cleaned['Duration'].sum()]
    })
    summary.to_excel(writer, index=False, sheet_name="Summary")

st.download_button(
    "Download Excel Report",
    buffer.getvalue(),
    file_name="advision_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# PDF Export (if available)
if HAS_PDF:
    def export_pdf_report(cleaned, duplicates, summary):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("AdVision Tracker - Shift Report", styles['Title']))
        elements.append(Spacer(1, 12))

        for _, row in summary.iterrows():
            elements.append(Paragraph(f"<b>{row['Metric']}</b>: {row['Value']}", styles['Normal']))
        elements.append(Spacer(1, 12))

        if not cleaned.empty:
            data = [cleaned.columns.tolist()] + cleaned.head(10).values.tolist()
            table = Table(data)
            table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.black)]))
            elements.append(Paragraph("Cleaned Ads (Sample):", styles['Heading2']))
            elements.append(table)
            elements.append(Spacer(1, 12))

        if not duplicates.empty:
            data = [duplicates.columns.tolist()] + duplicates.head(5).values.tolist()
            table = Table(data)
            table.setStyle(TableStyle([("GRID", (0,0), (-1,-1), 0.5, colors.red)]))
            elements.append(Paragraph("Duplicates (Sample):", styles['Heading2']))
            elements.append(table)

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    summary = pd.DataFrame({
        "Metric": ["Total Ads", "Unique Brands", "Total Duration"],
        "Value": [len(cleaned), cleaned['Brand'].nunique(), cleaned['Duration'].sum()]
    })

    st.download_button(
        "Download PDF Report",
        export_pdf_report(cleaned, dupes, summary),
        file_name="advision_shift_report.pdf",
        mime="application/pdf"
    )
else:
    st.info("📄 PDF export not available (ReportLab not installed).")

# ------------------ Role Simulation ------------------
st.header("👩‍💻 Role Simulation - Data Entry")
st.markdown("Try coding an ad as if you’re on the job:")

with st.form("entry_form"):
    ch = st.selectbox("Channel", df["Channel"].unique())
    ad = st.text_input("Ad Title")
    brand = st.text_input("Brand")
    product = st.text_input("Product")
    duration = st.number_input("Duration (sec)", 10, 180, 30)
    submitted = st.form_submit_button("Submit Entry")

if submitted:
    st.success(f"Ad '{ad}' for {brand} coded successfully into database!")

# ------------------ Shift Countdown ------------------
st.header("⏰ Shift Countdown (Demo)")
shift_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
shift_end = shift_start + datetime.timedelta(hours=9)
time_left = shift_end - datetime.datetime.now()
st.write(f"Shift ends in: **{time_left}**")
