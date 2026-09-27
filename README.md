# Inhibit

[![CI](https://github.com/ak495867/Inhibit/actions/workflows/ci.yml/badge.svg)](https://github.com/ak495867/Inhibit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Inhibit is a local-first Python toolkit for quantitative factor research and historical portfolio simulation. It makes data timing, chronological validation, trading costs, partial fills, and run reproducibility explicit. It is a research tool, not a broker, investment adviser, or production trading system.

> Historical results do not guarantee future performance. Review data provenance, assumptions, and model risk independently. This project does not provide personalized financial advice.

## Capabilities

- Ingest normalized OHLCV data from CSV, Parquet, JSON, and newline-delimited JSON; optionally download public data through yfinance.
- Track observation availability separately from its timestamp and apply an information buffer to feature construction.
- Build built-in or registered custom factors and evaluate bounded factor combinations with false-discovery controls.
- Use chronological walk-forward splits with purge and embargo windows rather than random train/test shuffling.
- Simulate commissions, spread, market impact, participation limits, stochastic fills, partial fills, and high-volatility or tail-risk stress.
- Export a run manifest, factor candidate ledger, target weights, fills, equity history, and artifact fingerprints.
- Inspect input data, validate YAML configuration, and verify a run's recorded artifacts and optional input fingerprint.

## Requirements and installation

Python 3.11 or later is required. Install the project and optional data/research dependencies in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[all]'
```

Optional dependency groups are available:

- `pip install -e .` installs the core engine.
- `pip install -e '.[data]'` adds yfinance downloads and Parquet support.
- `pip install -e '.[research]'` adds SciPy and statsmodels research utilities.
- `pip install -e '.[dev]'` adds pytest, Ruff, and mypy.

## Quick start: validate and run a local dataset

Your input must contain `symbol`, `timestamp`, `open`, `high`, `low`, `close`, and `volume`. Example rows and the full input contract are described in [usage.md](usage.md).

```bash
inhibit inspect --input data/prices.csv
inhibit validate-config --config configs/example.yml
inhibit run --config configs/example.yml --input data/prices.csv --output runs/example
inhibit verify --run runs/example --input data/prices.csv
```

Input paths may be CSV, Parquet (`.parquet` or `.pq`), JSON records, or JSON Lines (`.jsonl` or `.ndjson`). Parquet needs `pyarrow`, which is included in the `data` and `all` extras.

## Quick start: public yfinance data

```bash
inhibit fetch-yfinance \
  --symbols AAPL MSFT NVDA \
  --start 2018-01-01 \
  --end 2025-01-01 \
  --output data/us_large_caps.parquet

inhibit run \
  --config configs/example.yml \
  --input data/us_large_caps.parquet \
  --output runs/yfinance_example
```

Provider coverage, corporate-action handling, historical universe membership, and licensing vary. A downloaded dataset is not point-in-time safe merely because it came from a public provider. In particular, a present-day constituent list used on past dates creates survivorship risk.

## Command reference

| Command | Purpose |
| --- | --- |
| `inhibit inspect --input FILE` | Normalize and summarize a dataset; return a non-zero status when integrity checks report issues. |
| `inhibit validate-config --config FILE` | Load and validate a YAML research configuration. |
| `inhibit fetch-yfinance --symbols ... --start DATE --end DATE --output FILE` | Download public OHLCV data; CSV is the default output and Parquet is selected by the output suffix. |
| `inhibit run --config FILE --input FILE --output DIR` | Run chronological factor research and write reproducibility artifacts. |
| `inhibit verify --run DIR [--input FILE]` | Check recorded artifact hashes and, when supplied, the input file hash. |

Run `inhibit --help` or `inhibit COMMAND --help` for command-line options.

## Configuration and research workflow

Start with [`configs/example.yml`](configs/example.yml). Review its feature list, universe filters, information buffer, split windows, execution assumptions, and output settings before running. A minimal run is:

```bash
inhibit validate-config --config configs/example.yml
inhibit run --config configs/example.yml --input data/prices.csv --output runs/baseline
```

Recommended review sequence:

1. Keep the original source file and document its provider, vintage, adjustment policy, and known gaps.
2. Run `inhibit inspect` and resolve schema or integrity problems before analysis.
3. Validate the YAML and confirm that feature names and validation windows match the data you have.
4. Run the experiment with non-zero and defensible execution costs.
5. Review `manifest.json`, `candidates.csv`, `equity.csv`, and `fills.csv`; check leakage audits, candidate selection, out-of-sample windows, turnover, fill ratio, drawdown, and cost sensitivity.
6. Verify the output files with `inhibit verify` and preserve the exact configuration and input data.
7. Use a genuinely untouched holdout period for final evaluation; do not repeatedly tune against it.

The built-in defaults and example configuration are starting points, not guarantees that an experiment is well powered or appropriate for a particular market.

## Run artifacts

A successful research run writes:

| File | Contents |
| --- | --- |
| `manifest.json` | Configuration and input fingerprints, code/runtime details, validation windows, assumptions, metrics, audits, and recorded artifact hashes. |
| `candidates.csv` | Candidate factor expressions and discovery statistics. |
| `equity.csv` | Simulated portfolio equity history, when available. |
| `fills.csv` | Requested and filled quantities, execution costs, and fill diagnostics. |
| `target_weights.csv` | Target portfolio weights submitted to the simulator. |

Verify files after copying or archiving a run:

```bash
inhibit verify --run runs/example --input data/prices.csv
```

Verification checks artifact paths, sizes, and hashes captured in the manifest. When `--input` is provided, it also compares that file's hash to the recorded input fingerprint.

## Documentation and examples

- [Practical usage guide](usage.md)
- [Architecture](docs/architecture.md)
- [Methodology and validation](docs/methodology.md)
- [Production-readiness boundary](docs/production_readiness.md)
- [Custom factor example](examples/custom_factor.py)
- [Example configuration](configs/example.yml)

## Development and CI

```bash
python -m pip install -e '.[dev]'
ruff format --check .
ruff check .
pytest
```

GitHub Actions runs dependency checks, formatting, linting, tests, and installed-CLI smoke tests on Python 3.11, 3.12, and 3.13. Each matrix run uploads a JUnit XML test artifact, including when a test step fails and a report was produced.

## Scope and limitations

Inhibit produces historical research outputs; it does not route live orders. Public data may contain survivorship, revision, corporate-action, timestamp, or licensing limitations. Simulated fills, costs, liquidity, and market impact are simplified models and may differ materially from real execution. A point-in-time field or manifest does not independently prove that a source dataset is complete or unbiased. Do not use a backtest as the sole basis for a financial decision.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
