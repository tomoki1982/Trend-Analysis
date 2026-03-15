from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import yfinance as yf


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config" / "indicators.json"
DATA_DIR = ROOT_DIR / "data"
HISTORY_PATH = DATA_DIR / "history.csv"
HISTORY_LITE_PATH = DATA_DIR / "history_lite.csv"
LATEST_PATH = DATA_DIR / "latest_snapshot.csv"
MIN_HISTORY_DATE = "2020-01-01"
HTTP_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; TrendAnalysisBot/1.0)"
DATASET_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "symbol",
    "indicator_name",
    "category",
    "region",
    "refresh",
    "source",
    "unit",
    "fetched_at",
]
HISTORY_LITE_COLUMNS = [
    "date",
    "indicator_name",
    "category",
    "region",
    "refresh",
    "close",
]


def load_indicator_config(path: Path = CONFIG_PATH) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def filter_indicators_by_refresh(indicators: Iterable[dict], refresh: str) -> list[dict]:
    return [indicator for indicator in indicators if indicator.get("refresh") == refresh]


def fetch_market_data(indicators: Iterable[dict], period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    for indicator in indicators:
        frame = fetch_indicator_frame(indicator, fetched_at=fetched_at, period=period, interval=interval)
        if frame.empty:
            continue
        frames.append(frame)

    if not frames:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    dataset = pd.concat(frames, ignore_index=True)
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        dataset[column] = pd.to_numeric(dataset[column], errors="coerce")

    dataset["date"] = pd.to_datetime(dataset["date"], errors="coerce")
    dataset = dataset.dropna(subset=["date", "close"])
    dataset = dataset[dataset["date"] >= pd.Timestamp(MIN_HISTORY_DATE)]
    dataset["date"] = dataset["date"].dt.strftime("%Y-%m-%d")
    dataset = dataset.drop_duplicates(subset=["symbol", "date"], keep="last")
    return dataset.sort_values(["indicator_name", "date"]).reset_index(drop=True)


def build_latest_snapshot(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return dataset.copy()

    ordered = dataset.sort_values(["indicator_name", "date"]).copy()
    ordered["prev_close"] = ordered.groupby("symbol")["close"].shift(1)
    latest = ordered.groupby("symbol", as_index=False).tail(1).copy()
    latest["change"] = latest["close"] - latest["prev_close"]
    latest["change_pct"] = (latest["change"] / latest["prev_close"]) * 100
    return latest.sort_values(["refresh", "category", "region", "indicator_name"]).reset_index(drop=True)


def save_csv(dataset: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(path, index=False, encoding="utf-8-sig")


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_history_lite(dataset: pd.DataFrame) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame(columns=HISTORY_LITE_COLUMNS)

    frame = dataset.copy()
    for column in HISTORY_LITE_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA

    lite = frame[HISTORY_LITE_COLUMNS].copy()
    lite["date"] = pd.to_datetime(lite["date"], errors="coerce")
    lite["close"] = pd.to_numeric(lite["close"], errors="coerce")
    lite = lite.dropna(subset=["date", "indicator_name", "close"])
    lite = lite[lite["date"] >= pd.Timestamp(MIN_HISTORY_DATE)]
    lite["date"] = lite["date"].dt.strftime("%Y-%m-%d")
    return lite.sort_values(["indicator_name", "date"]).reset_index(drop=True)


def build_segmented_history_exports(dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
    lite = build_history_lite(dataset)
    if lite.empty:
        return {}

    frame = lite.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])

    exports: dict[str, pd.DataFrame] = {}

    monthly = frame[frame["refresh"] == "monthly"].copy()
    if not monthly.empty:
        monthly["date"] = monthly["date"].dt.strftime("%Y-%m-%d")
        exports["history_monthly.csv"] = monthly.sort_values(["indicator_name", "date"]).reset_index(drop=True)

    daily = frame[frame["refresh"] == "daily"].copy()
    if not daily.empty:
        daily["year"] = daily["date"].dt.year
        for year, year_frame in daily.groupby("year"):
            output = year_frame.drop(columns=["year"]).copy()
            output["date"] = output["date"].dt.strftime("%Y-%m-%d")
            exports[f"history_daily_{year}.csv"] = output.sort_values(["indicator_name", "date"]).reset_index(drop=True)

    return exports


def fetch_indicator_frame(indicator: dict, fetched_at: str, period: str, interval: str) -> pd.DataFrame:
    source_type = indicator.get("source_type", "yahoo")
    if source_type == "yahoo":
        return fetch_yahoo_history(indicator, fetched_at=fetched_at, period=period, interval=interval)
    if source_type == "fred":
        return fetch_fred_series(indicator, fetched_at=fetched_at)
    if source_type == "fred_derived":
        return fetch_fred_derived_series(indicator, fetched_at=fetched_at)
    if source_type == "tradingeconomics_latest":
        return fetch_tradingeconomics_latest(indicator, fetched_at=fetched_at)
    return pd.DataFrame(columns=DATASET_COLUMNS)


def fetch_yahoo_history(indicator: dict, fetched_at: str, period: str, interval: str) -> pd.DataFrame:
    history = yf.download(
        tickers=indicator["symbol"],
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        multi_level_index=False,
    )
    if history.empty:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    frame = history.reset_index()
    frame.columns = [str(col) for col in frame.columns]
    frame = frame.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    return enrich_indicator_frame(frame, indicator, fetched_at)


def fetch_fred_series(indicator: dict, fetched_at: str) -> pd.DataFrame:
    series_id = indicator["series_id"]
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    frame = pd.read_csv(url)
    if frame.empty:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    normalized_columns = {column: str(column).strip() for column in frame.columns}
    frame = frame.rename(columns=normalized_columns)

    date_column = next((column for column in frame.columns if str(column).upper() == "DATE"), None)
    value_column = next((column for column in frame.columns if str(column).strip() == series_id), None)

    if date_column is None and len(frame.columns) >= 1:
        date_column = frame.columns[0]
    if value_column is None and len(frame.columns) >= 2:
        value_column = frame.columns[1]

    if date_column is None or value_column is None:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    frame = frame.rename(columns={date_column: "date", value_column: "close"})
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["close"])
    frame["open"] = frame["close"]
    frame["high"] = frame["close"]
    frame["low"] = frame["close"]
    frame["adj_close"] = frame["close"]
    frame["volume"] = pd.NA
    return enrich_indicator_frame(frame, indicator, fetched_at)


def fetch_fred_derived_series(indicator: dict, fetched_at: str) -> pd.DataFrame:
    series_ids = indicator.get("series_ids", [])
    if len(series_ids) != 2:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    left_indicator = dict(indicator)
    left_indicator["series_id"] = series_ids[0]
    right_indicator = dict(indicator)
    right_indicator["series_id"] = series_ids[1]

    left = fetch_fred_series(left_indicator, fetched_at=fetched_at)
    right = fetch_fred_series(right_indicator, fetched_at=fetched_at)
    if left.empty or right.empty:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    merged = left[["date", "close"]].rename(columns={"close": "left_close"}).merge(
        right[["date", "close"]].rename(columns={"close": "right_close"}),
        on="date",
        how="inner",
    )
    if indicator.get("formula") != "multiply":
        return pd.DataFrame(columns=DATASET_COLUMNS)

    merged["close"] = merged["left_close"] * merged["right_close"]
    merged["open"] = merged["close"]
    merged["high"] = merged["close"]
    merged["low"] = merged["close"]
    merged["adj_close"] = merged["close"]
    merged["volume"] = pd.NA
    return enrich_indicator_frame(
        merged[["date", "open", "high", "low", "close", "adj_close", "volume"]],
        indicator,
        fetched_at,
    )


def fetch_tradingeconomics_latest(indicator: dict, fetched_at: str) -> pd.DataFrame:
    response = requests.get(
        indicator["url"],
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    text = normalize_page_text(response.text)
    label = indicator.get("page_label", indicator["name"])
    value = extract_tradingeconomics_value(text, label)
    if value is None:
        return pd.DataFrame(columns=DATASET_COLUMNS)

    frame = pd.DataFrame(
        [
            {
                "date": datetime.now(timezone.utc).date().isoformat(),
                "open": value,
                "high": value,
                "low": value,
                "close": value,
                "adj_close": value,
                "volume": pd.NA,
            }
        ]
    )
    return enrich_indicator_frame(frame, indicator, fetched_at)


def normalize_page_text(html: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", without_tags)


def extract_tradingeconomics_value(text: str, label: str) -> float | None:
    label_pattern = re.escape(label)
    patterns = [
        rf"{label_pattern}.*?(?:fell to|rose to|increased to|decreased to|was at|was|stood at|traded at)\s+([0-9][0-9,]*(?:\.[0-9]+)?)",
        rf"{label_pattern}\s+[|-]\s+Price\s+[|-].*?([0-9][0-9,]*(?:\.[0-9]+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def enrich_indicator_frame(frame: pd.DataFrame, indicator: dict, fetched_at: str) -> pd.DataFrame:
    enriched = frame.copy()
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column not in enriched.columns:
            enriched[column] = pd.NA
    enriched["symbol"] = indicator["symbol"]
    enriched["indicator_name"] = indicator["name"]
    enriched["category"] = indicator["category"]
    enriched["region"] = indicator["region"]
    enriched["refresh"] = indicator.get("refresh", "")
    enriched["source"] = indicator["source"]
    enriched["unit"] = indicator.get("unit", "")
    enriched["fetched_at"] = fetched_at
    return enriched[DATASET_COLUMNS]


def merge_history_frames(existing: pd.DataFrame, new_data: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return new_data.copy()
    if new_data.empty:
        return existing.copy()

    existing_frame = existing.copy()
    new_frame = new_data.copy()
    for column in DATASET_COLUMNS:
        if column not in existing_frame.columns:
            existing_frame[column] = pd.NA
        if column not in new_frame.columns:
            new_frame[column] = pd.NA

    merged = pd.concat([existing_frame[DATASET_COLUMNS], new_frame[DATASET_COLUMNS]], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce")
    merged = merged.dropna(subset=["date"])
    merged = merged[merged["date"] >= pd.Timestamp(MIN_HISTORY_DATE)]
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    merged = merged.drop_duplicates(subset=["symbol", "date"], keep="last")
    return merged.sort_values(["indicator_name", "date"]).reset_index(drop=True)
