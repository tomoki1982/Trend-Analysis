# CGPI Import Steps

## 1. Download, extract, transform, and copy to clipboard

```powershell
cd "C:\Users\gotta\.codex\codexアプリ\Trend Analysis"
python scripts\process_cgpi_zip.py --copy
```

If you already downloaded the ZIP file locally, use:

```powershell
cd "C:\Users\gotta\.codex\codexアプリ\Trend Analysis"
python scripts\process_cgpi_zip.py --zip-file "C:\path\to\cgpi_m_jp.zip" --copy
```

## 2. Paste into the target Google Sheet

Target sheet:

https://docs.google.com/spreadsheets/d/1Iyh_wh7QUdEHKT6OzW_F5OFpkkLPfaaevlZbYxXfsLg/edit?gid=1057686744#gid=1057686744

1. Open the target tab.
2. Select cell `A1`.
3. Paste with `Ctrl + V`.

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
