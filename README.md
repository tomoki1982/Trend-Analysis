# Economic Index Dashboard

`Python -> GitHub -> Google Sheets -> Looker Studio` を前提にした無料構成のサンプルです。

## Overview

1. `scripts/fetch_indicators.py` が指標データを取得
2. `data/history.csv`, `data/history_lite.csv`, `data/latest_snapshot.csv` と分割CSVを更新
3. GitHub Actions が CSV を公開リポジトリへ push
4. Google Sheets が GitHub raw CSV を `IMPORTDATA()` で読み込み
5. Looker Studio が Sheets を参照して可視化

## Covered Indicators

- Domestic Corporate Goods Price Index
- Japan Manufacturing PMI
- USD/JPY
- EUR/USD
- EUR/JPY
- WTI Crude Oil
- Semiconductor Index (SOX)
- Baltic Dry Index

## Local Setup

```powershell
conda activate <your-env>
pip install -r requirements.txt
python scripts\fetch_indicators.py --refresh daily
python scripts\fetch_indicators.py --refresh monthly
streamlit run app.py
```

## Output Files

- `data/history.csv`: time series for Looker Studio trend charts
- `data/history_lite.csv`: lightweight time series for Google Sheets and Looker Studio
- `data/latest_snapshot.csv`: latest values table
- `data/history_monthly.csv`: monthly history for Google Sheets
- `data/history_daily_YYYY.csv`: daily history split by year for Google Sheets

## GitHub Actions

Workflow file: [update-market-data.yml](C:\Users\gotta\.codex\codexアプリ\Trend Analysis\.github\workflows\update-market-data.yml)

- Daily indicators: weekdays at 09:00 JST
- Monthly indicators: 1st day of month at 09:15 JST
- Manual run: GitHub Actions `workflow_dispatch`

## Google Sheets

Create two sheets in your spreadsheet and paste these formulas.

Monthly history sheet:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/USERNAME/REPOSITORY/main/data/history_monthly.csv")
```

Daily history sheets:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/USERNAME/REPOSITORY/main/data/history_daily_2020.csv")
```

年ごとに `2021`, `2022`, `2023`, `2024`, `2025`, `2026` も同様に読み込みます。

Latest sheet:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/USERNAME/REPOSITORY/main/data/latest_snapshot.csv")
```

Your target spreadsheet is:
[trend analysis](https://docs.google.com/spreadsheets/d/1Iyh_wh7QUdEHKT6OzW_F5OFpkkLPfaaevlZbYxXfsLg/edit?gid=0#gid=0)

## Looker Studio

Use the imported Sheets as data sources.

- Latest value table: use `latest_snapshot.csv`
- Trend chart: use the split daily sheets and monthly sheet
- Suggested dimensions: `indicator_name`, `category`, `region`, `refresh`, `date`
- Suggested metrics: `close`, `change`, `change_pct`

## Notes

- FRED series are pulled as historical series.
- PMI is scraped from a public page as a latest value and accumulated over time.
- BDI is fetched from Investing.com historical data and accumulated over time.
- Free data sources can change page structure, so periodic maintenance may be needed.
