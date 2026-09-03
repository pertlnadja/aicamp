from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DATA_DIR = Path("data/raw/vc_spectra")
OUTPUT_FILE = Path("data/processed/combined_measurements.parquet")

HEADER_META_LINES = 31
TABLE_HEADER_LINE = 32
DATA_START_LINE = 36


# ---------------------------------------------------------------------
# Filename parsing
# ---------------------------------------------------------------------

FILENAME_PATTERN = re.compile(
    r"""
    ^
    (?P<file_timestamp>\d{4}-\d{2}-\d{2}T\d{2}\.\d{2}\.\d{2}\.\d+)
    _
    (?P<machine>.+?)
    -
    (?P<material_number>M\d+)
    -
    (?P<device>\d+_\d+_\d+_\d+_\d+)
    _
    (?P<sensor>\d+)
    -
    (?P<workstep>\d+)
    -
    (?P<measurement_type>FFT|Stoss)
    $
    """,
    re.VERBOSE,
)


def parse_filename(path: Path) -> dict:
    """Extract metadata encoded in the filename."""

    match = FILENAME_PATTERN.match(path.stem)

    if match is None:
        raise ValueError(f"Could not parse filename: {path.name}")

    meta = match.groupdict()

    meta["file_timestamp"] = pd.to_datetime(
        meta["file_timestamp"],
        format="%Y-%m-%dT%H.%M.%S.%f",
    )

    meta["machine"] = meta["machine"].replace("_", " ")
    meta["sensor"] = int(meta["sensor"])
    meta["workstep"] = int(meta["workstep"])

    # Example:
    # 10_191_78_83_3321 -> 10.191.78.83:3321
    device_parts = meta["device"].split("_")

    if len(device_parts) == 5:
        meta["device"] = ".".join(device_parts[:4]) + ":" + device_parts[4]

    return meta


# ---------------------------------------------------------------------
# Header parsing
# ---------------------------------------------------------------------


def clean_column_name(name: str) -> str:
    """Convert metadata keys to simple column names."""

    name = name.strip().lower()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^0-9a-zA-Z_]+", "", name)

    return name


def parse_header(path: Path) -> dict:
    """
    Extract scalar metadata from lines 1-31.

    Only simple key-value rows are added to the dataframe.
    """

    metadata = {}

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.reader(f)

        for _ in range(HEADER_META_LINES):
            row = next(reader, None)

            if row is None:
                break

            values = [cell.strip() for cell in row if cell.strip()]

            if len(values) != 2:
                continue

            key, value = values

            key = f"header_{clean_column_name(key)}"

            metadata[key] = value

    return metadata


# ---------------------------------------------------------------------
# Structure validation
# ---------------------------------------------------------------------


def validate_structure(path: Path) -> None:
    """
    Validate the assumed file structure:

    lines 1-31   metadata
    line 32      table header
    lines 33-34  reference / warning rows
    line 35      blank
    line 36+     real measurements
    """

    with path.open(
        "r",
        encoding="utf-8-sig",
    ) as f:
        lines = f.readlines()

    if len(lines) < DATA_START_LINE:
        raise ValueError(f"{path.name}: file is shorter than expected")

    if not lines[TABLE_HEADER_LINE - 1].startswith("Timestamp"):
        raise ValueError(
            f"{path.name}: expected table header on line {TABLE_HEADER_LINE}"
        )

    if lines[34].strip() != "":
        raise ValueError(f"{path.name}: expected line 35 to be empty")


# ---------------------------------------------------------------------
# Read one file
# ---------------------------------------------------------------------


def read_measurement_file(path: Path) -> pd.DataFrame:
    """Read one measurement CSV and attach its metadata."""

    validate_structure(path)

    filename_meta = parse_filename(path)
    header_meta = parse_header(path)

    # -------------------------------------------------------------
    # Read the column names from line 32
    # -------------------------------------------------------------

    columns = pd.read_csv(
        path,
        skiprows=TABLE_HEADER_LINE - 1,
        nrows=0,
        encoding="utf-8-sig",
    ).columns

    # -------------------------------------------------------------
    # Read only the actual measurements from line 36 onward
    # -------------------------------------------------------------

    df = pd.read_csv(
        path,
        skiprows=DATA_START_LINE - 1,
        names=columns,
        encoding="utf-8-sig",
        low_memory=False,
    )

    # -------------------------------------------------------------
    # Normalize important data types
    # -------------------------------------------------------------

    df["Timestamp"] = pd.to_datetime(
        df["Timestamp"],
        unit="ms",
    )

    df["Alarmlevel"] = pd.to_numeric(
        df["Alarmlevel"],
        errors="raise",
    ).astype("int8")

    # -------------------------------------------------------------
    # Add filename metadata
    # -------------------------------------------------------------

    for key, value in filename_meta.items():
        df[key] = value

    # -------------------------------------------------------------
    # Add scalar metadata from the file header
    # -------------------------------------------------------------

    for key, value in header_meta.items():
        df[key] = value

    # Keep source filename for traceability
    df["source_file"] = path.name

    return df


# ---------------------------------------------------------------------
# Read whole folder
# ---------------------------------------------------------------------


def load_folder(data_dir: Path) -> pd.DataFrame:
    """Combine all CSV files in a folder into one dataframe."""

    files = sorted(data_dir.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No CSV files found in {data_dir.resolve()}")

    dataframes = []

    for path in files:
        try:
            df = read_measurement_file(path)
            dataframes.append(df)

        except Exception as exc:
            raise RuntimeError(f"Failed while reading {path.name}") from exc

    return pd.concat(
        dataframes,
        ignore_index=True,
        sort=False,
    )


# ---------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------


def constant_columns(df: pd.DataFrame) -> list[str]:
    """Return columns that contain only one distinct value."""

    return [column for column in df.columns if df[column].nunique(dropna=False) == 1]


def print_metadata_summary(df: pd.DataFrame) -> None:
    """Print number of distinct values in metadata columns."""

    metadata_columns = [
        column
        for column in df.columns
        if (
            column
            in {
                "source_file",
                "file_timestamp",
                "machine",
                "material_number",
                "device",
                "sensor",
                "workstep",
                "measurement_type",
            }
            or column.startswith("header_")
        )
    ]

    summary = pd.Series(
        {column: df[column].nunique(dropna=False) for column in metadata_columns},
        name="n_unique",
    ).sort_values()

    print("\nMetadata columns:")
    print(summary.to_string())


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

if __name__ == "__main__":
    df = load_folder(DATA_DIR)

    print()
    print(f"Rows:    {len(df):,}")
    print(f"Columns: {df.shape[1]:,}")
    print(f"Files:   {df['source_file'].nunique():,}")

    print_metadata_summary(df)

    print("\nConstant columns:")

    for column in constant_columns(df):
        print(f"  - {column}")

    df.to_parquet(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print(f"Saved to: {OUTPUT_FILE.resolve()}")
