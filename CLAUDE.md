# CLAUDE.md

You're working on a WSL.

## Project

CNC/grinding-machine vibration analysis. Raw FFT spectra exported per-sensor,
per-workstep from machine tools (Kapp KX260 Twin) get parsed into a combined
Parquet dataset, then visualized as time-frequency spectrograms.

Python 3.14, managed with `uv`. Dependencies: pandas, pyarrow, fastparquet, matplotlib.

## Commands

- Install/sync deps: `uv sync`
- Run a script: `uv run scripts/data_preprocessing.py` / `uv run scripts/analyse_data.py` / `uv run main.py`
- Add a dependency: `uv add <package>`

There is no test suite, linter, or formatter configured in this repo.

## Data pipeline

`data/` is gitignored — raw and processed data never enter version control.

1. **`scripts/data_preprocessing.py`** reads all CSVs from `data/raw/vc_spectra/`
   and combines them into `data/processed/combined_measurements.parquet`.
   - Filenames encode metadata (timestamp, machine, material number, device
     IP:port, sensor, workstep, measurement type) via `FILENAME_PATTERN` in
     `parse_filename`. Each source file has a fixed structure: lines 1-31 are
     scalar key/value metadata, line 32 is the data table header, lines 33-34
     are reference/warning rows, line 35 is blank, and line 36+ is the actual
     measurement data — `validate_structure` enforces these assumptions and
     raises if a file doesn't match, so a new file layout needs the constants
     at the top of the file (`HEADER_META_LINES`, `TABLE_HEADER_LINE`,
     `DATA_START_LINE`) and `FILENAME_PATTERN` updated together.
   - One row = one FFT spectrum; spectral bins are columns `Wert1..Wert1024`.
   - Run as a script (`if __name__ == "__main__"`), not imported as a library
     elsewhere — it prints a metadata/constant-column summary before writing
     the Parquet file.

2. **`scripts/analyse_data.py`** reads the combined Parquet file and plots
   time-frequency heatmaps (`plot_spectrograms_by_alarm`) for a given
   sensor/workstep, faceted into a 2x2 grid by `Alarmlevel` (-1, 0, 1, 2)
   with a shared color scale across panels. Frequency axis is derived from
   `frequency_resolution_hz` (bin width) rather than stored explicitly.

`main.py` is currently just the default `uv init` stub, unrelated to the
data pipeline above.