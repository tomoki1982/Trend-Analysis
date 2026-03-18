from __future__ import annotations

import argparse
import subprocess
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_URL = "https://www.stat-search.boj.or.jp/info/cgpi_m_jp.zip"
DEFAULT_OUTPUT_CSV = DATA_DIR / "cgpi_dashboard.csv"
DEFAULT_OUTPUT_TSV = DATA_DIR / "cgpi_dashboard.tsv"
TARGET_SERIES = {
    "企業物価指数 2020年基準/輸入物価指数/円ベース": "輸入物価指数/円ベース",
    "企業物価指数 2020年基準/消費税を除く国内企業物価指数": "消費税を除く国内企業物価指数",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-url", default=DEFAULT_URL)
    parser.add_argument("--zip-file")
    parser.add_argument("--output-csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--output-tsv", default=str(DEFAULT_OUTPUT_TSV))
    parser.add_argument("--copy", action="store_true", help="Copy TSV output to Windows clipboard")
    args = parser.parse_args()

    output_csv = Path(args.output_csv)
    output_tsv = Path(args.output_tsv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_tsv.parent.mkdir(parents=True, exist_ok=True)

    csv_path = extract_csv_from_zip(zip_file=args.zip_file, zip_url=args.zip_url)
    frame = load_cgpi_csv(csv_path)
    transformed = transform_cgpi(frame)

    transformed.to_csv(output_csv, index=False, encoding="utf-8-sig")
    transformed.to_csv(output_tsv, index=False, encoding="utf-8-sig", sep="\t")

    print(f"Rows: {len(transformed)}")
    print(f"CSV: {output_csv}")
    print(f"TSV: {output_tsv}")

    if args.copy:
        copy_file_to_clipboard(output_tsv)
        print("TSV copied to clipboard. Paste it into the target Google Sheet.")


def extract_csv_from_zip(zip_file: str | None, zip_url: str) -> Path:
    if zip_file:
        zip_path = Path(zip_file)
        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")
        return unzip_first_csv(zip_path.read_bytes())

    response = requests.get(zip_url, timeout=60)
    response.raise_for_status()
    return unzip_first_csv(response.content)


def unzip_first_csv(zip_bytes: bytes) -> Path:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as archive:
        csv_name = next((name for name in archive.namelist() if name.lower().endswith(".csv")), None)
        if csv_name is None:
            raise FileNotFoundError("No CSV file found inside the ZIP archive.")

        temp_dir = Path(tempfile.mkdtemp(prefix="cgpi_zip_"))
        extracted_path = temp_dir / Path(csv_name).name
        extracted_path.write_bytes(archive.read(csv_name))
        return extracted_path


def load_cgpi_csv(csv_path: Path) -> pd.DataFrame:
    encodings = ["cp932", "shift_jis", "utf-8-sig", "utf-8"]
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            return pd.read_csv(csv_path, encoding=encoding, dtype=str)
        except Exception as error:
            last_error = error

    raise RuntimeError(f"Failed to read CSV with supported encodings: {last_error}")


def transform_cgpi(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = frame.rename(
        columns={
            frame.columns[0]: "code",
            frame.columns[1]: "series_name",
            frame.columns[2]: "label_raw",
        }
    ).copy()

    renamed = renamed[renamed["series_name"].isin(TARGET_SERIES.keys())].copy()
    month_columns = [column for column in renamed.columns if str(column).isdigit() and len(str(column)) == 6]
    if not month_columns:
        raise ValueError("Monthly columns in YYYYMM format were not found.")

    melted = renamed.melt(
        id_vars=["code", "series_name", "label_raw"],
        value_vars=month_columns,
        var_name="yyyymm",
        value_name="close",
    )
    melted["close"] = pd.to_numeric(melted["close"], errors="coerce")
    melted = melted.dropna(subset=["close"]).copy()
    melted["date"] = pd.to_datetime(melted["yyyymm"] + "01", format="%Y%m%d")

    split_labels = melted["label_raw"].apply(split_label)
    melted["classification1"] = split_labels.str[0]
    melted["classification2"] = split_labels.str[1]
    melted["indicator_name"] = melted["series_name"].map(TARGET_SERIES)
    melted["category"] = "Inflation"
    melted["region"] = "Japan"
    melted["refresh"] = "monthly"
    melted["source"] = "Bank of Japan"
    melted["unit"] = "Index 2020=100"

    output = melted[
        [
            "date",
            "indicator_name",
            "classification1",
            "classification2",
            "close",
            "category",
            "region",
            "refresh",
            "source",
            "unit",
            "code",
            "series_name",
            "label_raw",
        ]
    ].copy()
    output["date"] = output["date"].dt.strftime("%Y-%m-%d")
    return output.sort_values(["indicator_name", "date", "classification1", "classification2"]).reset_index(drop=True)


def split_label(label: str) -> tuple[str, str]:
    cleaned = str(label).strip()
    if "総平均" in cleaned:
        return ("総平均", "")

    if "/" in cleaned:
        left, right = cleaned.split("/", 1)
        return (left.strip(), right.lstrip("_").strip())

    return (cleaned, "")


def copy_file_to_clipboard(file_path: Path) -> None:
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Set-Clipboard -Path '{file_path}'",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
