from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_pipeline import (
    HISTORY_PATH,
    HISTORY_LITE_PATH,
    LATEST_PATH,
    DATA_DIR,
    build_segmented_history_exports,
    build_history_lite,
    build_latest_snapshot,
    fetch_market_data,
    filter_indicators_by_refresh,
    load_csv,
    load_indicator_config,
    merge_history_frames,
    save_csv,
)


def main(refresh: str | None = None) -> None:
    indicators = load_indicator_config()
    if refresh:
        indicators = filter_indicators_by_refresh(indicators, refresh)

    dataset = fetch_market_data(indicators=indicators, period="1y", interval="1d")
    existing_history = load_csv(HISTORY_PATH)
    merged_history = merge_history_frames(existing_history, dataset)
    history_lite = build_history_lite(merged_history)
    segmented_exports = build_segmented_history_exports(merged_history)
    latest_snapshot = build_latest_snapshot(merged_history)
    latest_snapshot = latest_snapshot[latest_snapshot["refresh"] == "daily"].reset_index(drop=True)

    save_csv(merged_history, HISTORY_PATH)
    save_csv(history_lite, HISTORY_LITE_PATH)
    save_csv(latest_snapshot, LATEST_PATH)
    for filename, export_frame in segmented_exports.items():
        save_csv(export_frame, DATA_DIR / filename)

    print(f"Refresh target: {refresh or 'all'}")
    print(f"Fetched rows: {len(dataset)}")
    print(f"History rows: {len(merged_history)}")
    print(f"History lite rows: {len(history_lite)}")
    print(f"Segmented exports: {', '.join(sorted(segmented_exports.keys())) or '-'}")
    print(f"Latest snapshot rows: {len(latest_snapshot)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", choices=["daily", "monthly"])
    args = parser.parse_args()
    main(refresh=args.refresh)
