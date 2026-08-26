# Inhibit

Inhibit is a production-oriented, local-first research engine for adaptive quantitative factor models and tail-risk-aware execution research. It is built to make false edge difficult to manufacture: data availability timestamps are enforced, chronological validation is the default, trading frictions are explicit, partial fills are modeled, liquidity dry-ups and spread widening can be stressed, and every run emits a reproducibility manifest.

> Inhibit is research software. It does not guarantee profits, eliminate model risk, or provide personalized financial advice. Use paper trading, independent review, and appropriate controls before considering live deployment.

## What is included

| Area | Capability |
| --- | --- |
| Data | yfinance adapter plus CSV, Parquet, and JSON ingestion through one normalized schema. |
| Leakage control | Point-in-time `available_at` timestamps, information buffers, purge/embargo checks, and fail-closed validation. |
| Factors | Built-in momentum, reversal, volatility, liquidity, quality, value, and residualized factors. |
| Discovery | Bounded factor grammar, complexity penalties, stability filters, and nested walk-forward selection. |
| Simulation | Commission, dynamic spread, nonlinear impact, borrow fees, latency, participation caps, lot sizes, partial fills, liquidity dry-ups, and tail-risk slippage. |
| Validation | Walk-forward splits, out-of-sample metrics, bootstrap intervals, regime slices, turnover, capacity, and drawdown diagnostics. |
| Reproducibility | Configuration fingerprint, input-file fingerprints, code version, seed, assumptions, and run artifacts. |

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

## Quick start with a user file

The normalized price schema requires `symbol`, `timestamp`, `open`, `high`, `low`, `close`, and `volume`. Optional columns include `adj_close`, `currency`, `available_at`, and `source`; extra numeric columns such as `net_income`, `book_equity`, and `market_cap` remain available to custom factors. Timestamps are converted to UTC. For price data without an explicit `available_at`, Inhibit uses the bar timestamp plus the configured market-data publication lag. Universe eligibility is calculated row by row from prior observations, not from full-sample statistics.

```bash
inhibit inspect --input data/prices.csv
inhibit run --config configs/example.yml --input data/prices.csv --output runs/example
inhibit verify --run runs/example --input data/prices.csv
```

Parquet and JSON are accepted with the same column names. JSON may be a list of records or newline-delimited records.

## Quick start with yfinance

```bash
inhibit fetch-yfinance --symbols AAPL MSFT NVDA --start 2018-01-01 --end 2025-01-01 --output data/us_large_caps.parquet
inhibit run --config configs/example.yml --input data/us_large_caps.parquet --output runs/yf_example
```

Public data coverage, corporate actions, survivorship, and licensing vary by source. A downloaded dataset is not automatically point-in-time safe simply because it came from a reputable provider.

## Research workflow

1. Normalize and inspect the input data.
2. Define the universe, rebalance cadence, feature lookbacks, information buffer, and execution assumptions.
3. Run nested chronological validation with the baseline model included.
4. Review the generated report, especially leakage checks, costs, turnover, fill ratio, capacity stress, and regime results.
5. Repeat with an untouched holdout period and frozen research code.

## Data contract

The detailed schema and timing rules are in [`docs/architecture.md`](docs/architecture.md). Example configuration, including a `momentum_reversal_blend` custom rule, is in [`configs/example.yml`](configs/example.yml). The default engine assumes long-only portfolios, daily bars, next-bar execution, a 1-day information buffer for prices, and non-zero costs. Every default can be overridden in configuration, but zero-friction settings are rejected unless explicitly marked as a diagnostic run. Each run writes `manifest.json`, `candidates.csv`, `equity.csv`, `fills.csv`, and `target_weights.csv`; `inhibit verify` recomputes their hashes.

## Development

```bash
pytest
ruff format --check .
ruff check .
```

GitHub Actions runs the same formatting, lint, and test checks on Python 3.11 and 3.12 for pushes and pull requests. Each run uploads a JUnit XML test-results artifact. The locally verified release snapshot, including the PIT run verification and FDR results, is recorded in [`reports/ci/test_results.md`](reports/ci/test_results.md).

The code intentionally contains very few comments. A couple of the remaining comments are practical notes rather than an attempt to explain every line. Production-readiness boundaries are documented in [`docs/production_readiness.md`](docs/production_readiness.md).

## License

MIT. See [`LICENSE`](LICENSE).
