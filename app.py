from __future__ import annotations

import math
from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.data_pipeline import HISTORY_PATH, build_latest_snapshot, load_csv


st.set_page_config(page_title="Economic Index Dashboard", page_icon=":bar_chart:", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --card: rgba(255,255,255,0.80);
        --ink: #1f2a30;
        --muted: #6b7c85;
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(131, 197, 190, 0.45), transparent 30%),
            radial-gradient(circle at bottom right, rgba(255, 183, 3, 0.16), transparent 24%),
            linear-gradient(180deg, #f7f2e9 0%, #eef3f5 100%);
        color: var(--ink);
    }
    .hero {
        padding: 1.3rem 1.4rem;
        border: 1px solid rgba(0, 109, 119, 0.12);
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.52));
        backdrop-filter: blur(12px);
        margin-bottom: 1rem;
    }
    .metric-card {
        border-radius: 20px;
        padding: 1rem;
        background: var(--card);
        border: 1px solid rgba(31, 42, 48, 0.08);
        box-shadow: 0 12px 30px rgba(31, 42, 48, 0.06);
    }
    .metric-label {
        font-size: 0.85rem;
        color: var(--muted);
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900)
def load_dataset() -> pd.DataFrame:
    return normalize_dataset(load_csv(HISTORY_PATH))


def normalize_dataset(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return dataset

    frame = dataset.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["open", "high", "low", "close", "adj_close", "volume", "change", "change_pct"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date", "close"]).sort_values(["indicator_name", "date"]).reset_index(drop=True)


def format_number(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:.2f}"


dataset = load_dataset()

st.markdown(
    """
    <div class="hero">
      <h1>Economic Index Dashboard</h1>
      <p>GitHub public CSV based dashboard for FX, commodities, PMI, producer prices, SOX and BDI.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if dataset.empty:
    st.warning("No local CSV found. Run `python scripts/fetch_indicators.py` first.")
    st.stop()

latest_snapshot = build_latest_snapshot(dataset)
categories = sorted(dataset["category"].dropna().unique().tolist())
regions = sorted(dataset["region"].dropna().unique().tolist())
refresh_types = sorted(dataset["refresh"].dropna().unique().tolist())
max_date = dataset["date"].max().date()
min_date = dataset["date"].min().date()
default_start = max(min_date, max_date - timedelta(days=180))

with st.sidebar:
    st.header("Filter")
    selected_refresh = st.multiselect("Refresh", refresh_types, default=refresh_types)
    selected_categories = st.multiselect("Category", categories, default=categories)
    selected_regions = st.multiselect("Region", regions, default=regions)
    date_range = st.slider("Period", min_value=min_date, max_value=max_date, value=(default_start, max_date))

filtered = dataset[
    dataset["refresh"].isin(selected_refresh)
    & dataset["category"].isin(selected_categories)
    & dataset["region"].isin(selected_regions)
    & dataset["date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
]
latest_filtered = latest_snapshot[
    latest_snapshot["refresh"].isin(selected_refresh)
    & latest_snapshot["category"].isin(selected_categories)
    & latest_snapshot["region"].isin(selected_regions)
]

headline = latest_filtered.sort_values("change_pct", ascending=False, na_position="last").head(4)
metric_columns = st.columns(max(len(headline), 1))
for column, (_, row) in zip(metric_columns, headline.iterrows()):
    delta_value = row.get("change_pct")
    delta_text = "-" if pd.isna(delta_value) else f"{delta_value:+.2f}%"
    column.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{row["indicator_name"]}</div>
          <div class="metric-value">{format_number(row["close"])}</div>
          <div>{delta_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

tab1, tab2 = st.tabs(["Trend", "Latest Table"])

with tab1:
    chart = px.line(
        filtered,
        x="date",
        y="close",
        color="indicator_name",
        line_group="symbol",
        render_mode="svg",
        labels={"date": "Date", "close": "Value", "indicator_name": "Indicator"},
    )
    chart.update_layout(
        height=540,
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0.65)",
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(chart, use_container_width=True)

with tab2:
    columns = ["indicator_name", "category", "region", "refresh", "date", "close", "change", "change_pct", "unit", "source"]
    st.dataframe(latest_filtered[columns], use_container_width=True, hide_index=True)
