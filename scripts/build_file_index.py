"""Link vc_spectra and vc_stoss raw files at the part level.

Both a spectra CSV and a stoss CSV can cover several Bauteile (contiguous
`TeilNr` blocks) for one sensor+workstep -- spectra files are NOT one part
each (most hold 5, some 1-7; checked empirically across all 225 files). The
two datasets also sample at different cadences (~164ms vs ~120ms), so this
script does NOT align individual rows between them -- it only records, for
each (sensor, workstep, TeilNr), which spectra file and which stoss file
belong together. See data/README_data.md for the raw file layout this
assumes.

Run as a script (`if __name__ == "__main__"`), not imported elsewhere -- same
convention as scripts/data_preprocessing.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

SPECTRA_DIR = Path("data/raw/vc_spectra")
STOSS_DIR = Path("data/raw/vc_stoss")
OUTPUT_FILE = Path("data/processed/spectra_stoss_index.parquet")

TABLE_HEADER_LINE = 32
DATA_START_LINE = 36

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
    """Extract sensor/workstep encoded in the filename."""

    match = FILENAME_PATTERN.match(path.stem)

    if match is None:
        raise ValueError(f"Could not parse filename: {path.name}")

    meta = match.groupdict()
    meta["sensor"] = int(meta["sensor"])
    meta["workstep"] = int(meta["workstep"])

    return meta


def read_timestamp_and_teilnr(path: Path) -> pd.DataFrame:
    """Read only Timestamp + TeilNr from the real measurement rows (line 36+)."""

    columns = pd.read_csv(
        path,
        skiprows=TABLE_HEADER_LINE - 1,
        nrows=0,
        encoding="utf-8-sig",
    ).columns

    df = pd.read_csv(
        path,
        skiprows=DATA_START_LINE - 1,
        names=columns,
        usecols=["Timestamp", "TeilNr"],
        encoding="utf-8-sig",
    )
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], unit="ms")

    return df


def summarize_file(path: Path, prefix: str) -> list[dict]:
    """One file can cover several Bauteile -- one output row per TeilNr block."""

    meta = parse_filename(path)
    df = read_timestamp_and_teilnr(path)

    rows = []

    for teilnr, group in df.groupby("TeilNr"):
        rows.append(
            {
                "sensor": meta["sensor"],
                "workstep": meta["workstep"],
                "TeilNr": int(teilnr),
                f"{prefix}_file": path.name,
                f"{prefix}_time_start": group["Timestamp"].min(),
                f"{prefix}_time_end": group["Timestamp"].max(),
                f"{prefix}_n_rows": len(group),
            }
        )

    return rows


def build_index() -> pd.DataFrame:
    spectra_files = sorted(SPECTRA_DIR.glob("*.csv"))
    stoss_files = sorted(STOSS_DIR.glob("*.csv"))

    if not spectra_files:
        raise FileNotFoundError(f"No CSV files found in {SPECTRA_DIR.resolve()}")

    if not stoss_files:
        raise FileNotFoundError(f"No CSV files found in {STOSS_DIR.resolve()}")

    spectra_df = pd.DataFrame(
        row for p in spectra_files for row in summarize_file(p, "spectra")
    )
    stoss_df = pd.DataFrame(
        row for p in stoss_files for row in summarize_file(p, "stoss")
    )

    # A given (sensor, workstep, TeilNr) should show up in at most one
    # file/TeilNr block per side -- surface it loudly if that ever breaks,
    # rather than silently picking one during the merge.
    for name, frame in [("spectra", spectra_df), ("stoss", stoss_df)]:
        dupe_mask = frame.duplicated(subset=["sensor", "workstep", "TeilNr"], keep=False)

        if dupe_mask.any():
            raise ValueError(
                f"Multiple {name} file/TeilNr blocks share the same "
                f"(sensor, workstep, TeilNr):\n{frame[dupe_mask]}"
            )

    merged = spectra_df.merge(
        stoss_df,
        on=["sensor", "workstep", "TeilNr"],
        how="inner",
        validate="one_to_one",
    )

    print(f"Spectra files:                            {len(spectra_files):,}")
    print(f"Stoss files:                              {len(stoss_files):,}")
    print(f"Spectra file/TeilNr blocks:               {len(spectra_df):,}")
    print(f"Stoss file/TeilNr blocks:                 {len(stoss_df):,}")
    print(f"Matched (spectra, stoss) TeilNr pairs:    {len(merged):,}")
    print(f"Spectra blocks dropped (no stoss match):  {len(spectra_df) - len(merged):,}")

    return merged


if __name__ == "__main__":
    index = build_index()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    index.to_parquet(OUTPUT_FILE, index=False)

    print(f"\nSaved to: {OUTPUT_FILE.resolve()}")
