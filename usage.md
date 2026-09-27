# Inhibit Usage Guide

This guide walks through preparing data, validating a configuration, running an experiment, and checking its artifacts. Inhibit is for local quantitative research and historical simulation; it is not a live trading system or financial advice.

## 1. Install

Python 3.11 or later is required. Create an isolated environment and install the full set of optional data, research, and development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[all]'
inhibit --help
```

For a smaller installation, use `pip install -e .` for core CSV/JSON research, `pip install -e '.[data]'` for yfinance and Parquet support, or `pip install -e '.[dev]'` for the test and style tools.

## 2. Prepare an input file

Supported input formats are CSV, Parquet (`.parquet` and `.pq`), JSON arrays of records, JSON objects with a `data` list, and newline-delimited JSON (`.jsonl` and `.ndjson`). Parquet support requires `pyarrow`.

The required columns are:

| Column | Meaning |
| --- | --- |
| `symbol` | Instrument identifier. Values are trimmed and normalized to uppercase. |
| `timestamp` | Bar timestamp. Values are parsed as UTC. |
| `open`, `high`, `low`, `close` | Positive OHLC prices. |
| `volume` | Non-negative volume. |

Optional columns include `adj_close`, `available_at`, `currency`, `source`, and `data_quality`. Additional columns are retained, which can be useful for custom factors. `available_at` describes when a value could have been known; if it is omitted for price bars, the loader sets it from `timestamp` plus the selected publication lag. Do not use the event timestamp as a substitute for the release time of fundamentals or alternative data.

Example CSV:

```csv
symbol,timestamp,open,high,low,close,volume,available_at
AAA,2024-01-02,49.8,51.0,49.5,50.5,120000,2024-01-02T21:00:00Z
AAA,2024-01-03,50.5,51.2,50.1,50.9,110000,2024-01-03T21:00:00Z
```

Inspect the file before research:

```bash
inhibit inspect --input data/prices.csv
```

The command prints a JSON summary with row and symbol counts, time bounds, and integrity issues. The normalizer rejects missing or malformed required values, non-finite prices/volume, non-positive prices, negative volume, and availability times before their corresponding timestamps. Inspect output is not a substitute for reviewing source quality, duplicates, adjustment policies, or point-in-time provenance.

## 3. Fetch public data (optional)

Install the `data` extra, then fetch a small sample:

```bash
inhibit fetch-yfinance \
  --symbols AAPL MSFT NVDA \
  --start 2018-01-01 \
  --end 2025-01-01 \
  --output data/us_large_caps.parquet
```

Use a `.csv` output path for CSV. The command creates missing parent directories. Provider downloads can be incomplete, revised, adjusted differently, or subject to usage terms. Preserve the downloaded file and record the provider, retrieval time, requested dates, and adjustment choice. Current constituents applied historically introduce survivorship bias.

## 4. Validate the configuration

The starter configuration is [`configs/example.yml`](configs/example.yml). It provides a list of input features and explicit validation, portfolio, and execution settings. Check it before a run:

```bash
inhibit validate-config --config configs/example.yml
```

On success, the command prints the configuration name and seed. Missing or duplicate feature names, invalid windows, impossible probability bounds, negative trading costs, non-finite values, or other invalid ranges cause a validation error.

For a first custom run, make a copy of the example file and adjust:

- `features.include` to names supported by the built-in feature registry or your registered custom feature workflow.
- `universe` minimum price, minimum history, liquidity, and position count to match your dataset.
- `schedule` label horizon, information buffer, and execution delay to match your decision timeline.
- `validation` train, validation, test, step, embargo, and minimum test-period settings to match the available history.
- `portfolio` position, leverage, and turnover limits.
- `execution` commissions, spread, impact, participation, fill assumptions, and optional stress behavior.

A syntactically valid configuration is not automatically appropriate for a dataset. The full dataclass defaults and configuration example are available in [`src/inhibit/config.py`](src/inhibit/config.py) and `configs/`.

## 5. Run an experiment

```bash
inhibit run \
  --config configs/example.yml \
  --input data/prices.csv \
  --output runs/example
```

The command reports a compact JSON summary containing the output path, metrics, and selected factors. Runs need enough chronological observations to produce the configured number of test windows. If the available history is too short, reduce the requested windows only when doing so remains statistically defensible; do not disguise a lack of out-of-sample evidence by relaxing safeguards.

For a public data file:

```bash
inhibit run \
  --config configs/example.yml \
  --input data/us_large_caps.parquet \
  --output runs/yfinance_example
```

## 6. Review the output

| Artifact | Review purpose |
| --- | --- |
| `manifest.json` | Check input/config fingerprints, code version, validation windows, feature audit, selected factor set, costs, metrics, and warnings. |
| `candidates.csv` | Review the full factor-discovery ledger, selection flags, and candidate statistics rather than only the winning candidate. |
| `equity.csv` | Inspect simulated equity through the test periods, if the run produced equity rows. |
| `fills.csv` | Inspect requested versus filled quantity, fill reasons, and costs. |
| `target_weights.csv` | Inspect target weights before execution constraints and fills. |

Start with availability/leakage audits and the actual train/validation/test windows. Then compare the baseline with selected factors, inspect consistency across test windows, drawdown, volatility, turnover, fill ratio, concentration, and sensitivity to higher costs. Treat wide confidence intervals or a result concentrated in one period as weak evidence.

## 7. Verify artifacts

Verify the run manifest and output hashes:

```bash
inhibit verify --run runs/example
```

Also compare the recorded input fingerprint when the original input is available:

```bash
inhibit verify --run runs/example --input data/prices.csv
```

The command returns a JSON object with `passed`, checked files, and failures; its process status is non-zero when a check fails. Keep the input, config, and run directory together when archiving experiments.

## 8. Custom factors and rules

The feature registry supports programmatic custom factor functions. A factor function receives a normalized pandas DataFrame and returns a Series aligned to its index. For time-series calculations, group and sort by symbol, use only information available at the decision time, and account for the configured information buffer.

```python
import pandas as pd

from inhibit.features.engine import FeatureEngine


def three_day_range(frame: pd.DataFrame) -> pd.Series:
    range_pct = (frame["high"] - frame["low"]) / frame["close"]
    return (
        range_pct.groupby(frame["symbol"], sort=False)
        .rolling(3, min_periods=3)
        .mean()
        .reset_index(level=0, drop=True)
    )


engine = FeatureEngine()
engine.registry.register("three_day_range", three_day_range)
```

The custom function must be registered in the Python process that builds the features. YAML `custom_rules` combine named factors with explicit weights; they do not import arbitrary Python functions. See [`examples/custom_factor.py`](examples/custom_factor.py) and the custom-rule section in [`configs/example.yml`](configs/example.yml).

## 9. Troubleshooting

- **`install inhibit[data]` message:** install `pip install -e '.[data]'` in the active environment.
- **Parquet reader/writer error:** install `pyarrow` with `pip install pyarrow` or install the `data` extra.
- **Missing required columns:** rename source fields to `symbol`, `timestamp`, `open`, `high`, `low`, `close`, and `volume` before retrying.
- **Availability/leakage rejection:** use conservative data availability timestamps and check the information buffer; do not simply disable the audit to make a run pass.
- **Not enough test windows:** the dataset may not cover the configured training, validation, test, embargo, and label-horizon requirements. Confirm that reducing windows preserves meaningful out-of-sample testing.
- **Unknown factor:** check the names in `features.include` against built-in factors in `src/inhibit/features/builtins.py`, or register the custom factor before invoking the feature engine.
- **Verification failure:** do not edit or overwrite run files after generation; regenerate the run or preserve an untouched copy of the original artifacts.

## 10. Development checks

```bash
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
pytest
```

The GitHub Actions workflow runs dependency checks, formatting, lint, tests, and CLI smoke tests on Python 3.11, 3.12, and 3.13.

## Research and deployment boundary

Backtests are sensitive to data quality, survivorship, corporate actions, repeated experimentation, and execution assumptions. Preserve an untouched holdout, account for multiple testing, and validate with independent data and code review. Inhibit's simulator is not a broker integration and does not implement the operational controls required for live trading. Do not use results as a promise of future returns or as personalized financial advice.
