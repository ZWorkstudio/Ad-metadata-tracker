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
  background: linear-gradient(90d...
