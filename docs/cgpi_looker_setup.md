# CGPI Monthly Setup

## What is updated automatically

GitHub Actions now runs `scripts/process_cgpi_zip.py` once a month and updates:

- `data/cgpi_dashboard.csv`

Raw URL:

`https://raw.githubusercontent.com/tomoki1982/Trend-Analysis/main/data/cgpi_dashboard.csv`

## Google Sheets formula

Create a new sheet such as `cgpi_monthly` and paste this into cell `A1`:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/tomoki1982/Trend-Analysis/main/data/cgpi_dashboard.csv")
```

If the sheet caches old content, use:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/tomoki1982/Trend-Analysis/main/data/cgpi_dashboard.csv?v=2")
```

## Recommended Looker Studio fields

- Dimension: `date`
- Breakdown dimension: `indicator_name`
- Optional breakdown: `classification1` or `classification2`
- Metric: `close`

## Output columns

- `date`
- `indicator_name`
- `classification1`
- `classification2`
- `close`
- `category`
- `region`
- `refresh`
- `source`
- `unit`
- `code`
- `series_name`
- `label_raw`
