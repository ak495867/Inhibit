# Inhibit Usage Guide

Inhibit is a local-first research engine for leakage-safe adaptive factor models. It accepts public data downloaded through the optional yfinance adapter and user-owned CSV, Parquet, JSON, or newline-delimited JSON files. It produces a reproducible research run rather than a live trading system.

> Historical simulations are hypotheses tests. They are not guarantees of future performance or personalized financial advice.

## 1. Installation

Create an isolated environment and install the package with the optional data and development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

The minimal installation is sufficient for CSV/JSON research, while `inhibit[data]` adds yfinance and Parquet support. The development extras add pytest, Ruff, and mypy.

## 2. Input data

A normalized price file must contain the following fields:

| Field | Required | Meaning |
|---|---:|---|
| `symbol` | Yes | Instrument identifier. |
| `timestamp` | Yes | Bar timestamp; converted to UTC. |
| `open` | Yes | Opening price. |
| `high` | Yes | High price. |
| `low` | Yes | Low price. |
| `close` | Yes | Closing price. |
| `volume` | Yes | Reported volume. |
| `adj_close` | No | Adjusted close retained separately from raw close. |
| `available_at` | No | Earliest point-in-time availability timestamp. |
| `currency` | No | Price currency. |
| `source` | No | Source identifier. |

Extra columns are retained. This allows factor inputs such as `net_income`, `book_equity`, `market_cap`, sector tags, or user-defined fields to travel with the price frame. For fundamentals and alternative data, provide a conservative `available_at` timestamp instead of relying on the event timestamp.

Inspect a local file before running a research job:

```bash
inhibit inspect --input data/prices.csv
```

The command reports row count, symbol count, time range, and integrity issues. Inhibit rejects missing required columns, invalid timestamps, non-positive prices, negative volume, impossible high/low relationships, and availability timestamps earlier than their events.

## 3. Public data through yfinance

With the data extra installed, download a public OHLCV dataset:

```bash
inhibit fetch-yfinance \
  --symbols AAPL MSFT NVDA \
  --start 2018-01-01 \
  --end 2025-01-01 \
  --output data/us_large_caps.parquet
```

Public data coverage, adjustments, historical membership, and licensing differ by provider. A download is not automatically point-in-time safe. For serious research, preserve the original file and record its vintage and adjustment policy.

## 4. Run a baseline experiment

Use the supplied conservative configuration:

```bash
inhibit run \
  --config configs/example.yml \
  --input data/prices.csv \
  --output runs/example
```

The default configuration uses lagged daily factors, one-bar execution delay, an information buffer, non-zero commissions, spread and impact, participation limits, probabilistic fills, a turnover cap, a minimum number of independent test windows, 21-bar block-bootstrap intervals, and 5% Benjamini–Hochberg false-discovery-rate control. Runs with Sharpe above 5 or annualized volatility below 1% are automatically flagged as possible verification artifacts.

## 5. Configure custom factors

A custom factor is a function that accepts the normalized DataFrame and returns a pandas Series aligned to its index. Register it before building features:

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

Custom factors should use lagged observations and must not read future rows. The feature engine applies the configured information buffer, cross-sectional winsorization, and standardization, then records a feature audit.

## 6. Configure custom multi-factor rules

A `MultiFactorCombinationRule` combines two or more named factors with explicit weights. It validates factor count, weight count, unique names, and non-zero weights:

```python
from inhibit.models.rules import MultiFactorCombinationRule

rule = MultiFactorCombinationRule(
    name="range_adjusted_momentum",
    factors=("momentum_12_1", "three_day_range"),
    weights=(1.0, -0.25),
    normalize=True,
)
```

Rules can also be declared in YAML:

```yaml
features:
  discovery:
    custom_rules:
      - name: momentum_reversal_blend
        factors: [momentum_12_1, reversal_1]
        weights: [0.70, -0.30]
        normalize: true
```

The adaptive discovery engine evaluates custom rules alongside its generated expression grammar. Each candidate receives a name, expression, complexity, mean rank information coefficient, median rank information coefficient, stability, observation count, and selection flag.

## 7. Wider symbolic-expression search

`configs/wide_search_stress.yml` enables `max_depth: 3`, 250 candidate slots, unary transforms such as `abs`, `square`, `log1p_abs`, and `sign`, protected ratios through `safe_div`, pairwise expressions, three-factor expressions, and a custom stress-aware blend. The evaluator is deliberately restricted to a safe expression grammar rather than unrestricted Python evaluation.

Run it with:

```bash
inhibit run \
  --config configs/wide_search_stress.yml \
  --input data/prices.csv \
  --output runs/wide_search_stress
```

A wider search increases the multiple-testing burden. Candidate p-values are adjusted with Benjamini–Hochberg FDR control before a discovery can replace the baseline. If no candidate passes, Inhibit records `baseline_fallback_no_fdr_pass` and fits the configured baseline factor set. Treat the candidate ledger and untouched holdout as mandatory review artifacts, not optional output.

## 8. Execution handlers and high-volatility stress

The simulator supports a default handler and a dynamic `high_volatility_stress` handler. Select the stress handler in YAML:

```yaml
execution:
  handler: high_volatility_stress
  spread_bps: 5.0
  impact_bps: 10.0
  participation_rate: 0.10
  fill_probability: 0.85
  stress_volatility_threshold: 0.012
  stress_spread_multiplier: 2.5
  stress_impact_multiplier: 4.0
  stress_participation_multiplier: 0.75
  stress_fill_probability_floor: 0.25
  stress_fill_probability_sensitivity: 0.60
  tail_risk_threshold: 0.05
  tail_spread_multiplier: 4.0
  tail_impact_multiplier: 6.0
  tail_liquidity_multiplier: 0.85
  tail_fill_probability_floor: 0.05
```

The handler uses realized volatility and the current bar range to raise spread and impact, reduce effective participation, and reduce fill probability subject to a floor. When volatility exceeds `tail_risk_threshold`, the tail-risk component widens spread and impact superlinearly, collapses effective liquidity through `tail_liquidity_multiplier`, throttles participation, and applies a separate fill-probability floor. Fill records include volatility level, stress factor, tail-risk factor, liquidity factor, effective spread, effective impact, effective participation, and effective fill probability. Partial fills persist residual rebalancing pressure and expire after `max_fill_bars`.

A custom handler can be injected directly:

```python
from inhibit.backtest.execution import ExecutionSimulator
from inhibit.backtest.handlers import ExecutionHandler

simulator = ExecutionSimulator(execution_config, portfolio_config, seed=42, handler=my_handler)
result = simulator.run(bars, target_weights)
```

For a severe tail-event stress run, use the supplied configuration:

```bash
inhibit run \
  --config configs/tail_risk_extreme.yml \
  --input data/prices.csv \
  --output runs/tail_risk_extreme
```

A live execution handler would require broker acknowledgements, durable order state, reconciliation, idempotency, kill switches, and risk controls. The historical handler is not a broker integration.

## 9. Generated artifacts

Every run writes the following files:

| Artifact | Purpose |
|---|---|
| `manifest.json` | Configuration hash, source fingerprint, commit, split records, metrics, assumptions, runtime versions, audits, and artifact hashes. |
| `candidates.csv` | Full factor-expression metric breakdown and selection flags. |
| `equity.csv` | Simulated equity, cash, marked positions, gross exposure, and borrow fees. |
| `fills.csv` | Requested and filled shares, costs, dynamic execution fields, and fill reasons. |
| `target_weights.csv` | Target portfolio instructions before execution. |

Verify the run and input data:

```bash
inhibit verify \
  --run runs/example \
  --input data/prices.csv
```

The command exits non-zero if an artifact is missing, altered, or no longer matches the recorded source fingerprint.

## 10. Interpreting results

Review `feature_audit` first. Any availability or future-price violation invalidates the run. Next review `split_count`, `baseline_rank_ic`, the candidate ledger, test-window consistency, turnover, fill ratio, maximum drawdown, friction assumptions, regime slices, and bootstrap intervals. A high point estimate with a wide confidence interval or a single-window result should be treated as weak evidence.

The manifest reports the selected factor, not necessarily the custom rule. A custom rule is allowed to lose. Forcing selection would undermine the purpose of adaptive discovery.

## 11. Full development checks

From the repository root:

```bash
ruff format .
ruff check .
PYTHONPATH=src pytest -q
```

The repository includes tests for schema rejection, feature warm-up and leakage barriers, disjoint purged/embargoed splits, partial fills, custom-rule discovery, end-to-end manifests, stress-handler slippage, and artifact verification.

## 12. Real S&P 500 yfinance workflow

The repository includes `scripts/download_sp500_yfinance.py`, which snapshots the current S&P 500 constituent table, downloads daily history in bounded batches, records failed symbols, and writes a source metadata file. The workflow is:

```bash
python scripts/download_sp500_yfinance.py \
  --start 2015-01-01 \
  --end 2026-08-01 \
  --output data/sp500_yfinance_2015_2026.csv \
  --universe-output data/sp500_universe_snapshot.json
python scripts/clean_yfinance_data.py \
  --input data/sp500_yfinance_2015_2026.csv \
  --output data/sp500_yfinance_2015_2026_clean.csv \
  --report data/sp500_yfinance_cleaning_report.json
inhibit run \
  --config configs/real_sp500.yml \
  --input data/sp500_yfinance_2015_2026_clean.csv \
  --output runs/real_sp500
```

This uses a current-constituent snapshot and therefore has survivorship bias when applied to earlier years. It is a real-data validation run, not a point-in-time historical index-membership study. Review the cleaning report and source metadata before interpreting results.

## 13. Production boundary

Inhibit is complete as a reproducible research system, not as a live trading operation. Before live capital is considered, add licensed point-in-time data, historical universe membership, a broker or exchange adapter, durable order and fill state, reconciliation, market calendars, exposure limits, kill switches, secrets management, monitoring, alerting, paper-trading evidence, and independent code and risk review. See [`production_readiness.md`](production_readiness.md) for the release boundary.
