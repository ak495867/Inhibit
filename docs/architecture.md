# Inhibit Architecture

Inhibit is a local-first, reproducible quantitative research platform for discovering and evaluating cross-sectional factor models. It is designed for research and paper trading, not unattended capital deployment. A model is considered credible only when its edge survives strict information-time controls, out-of-sample evaluation, realistic execution assumptions, costs, turnover constraints, and sensitivity analysis.

## Design principles

| Principle | Implementation consequence |
| --- | --- |
| Information time is distinct from event time | Every observation can carry `available_at`; features are only usable after that timestamp. |
| No silent look-ahead | Feature builders declare their required history and the engine applies an embargo before labels and fills. |
| Research is walk-forward | Training, validation, embargo, and test windows are generated chronologically; random shuffles are prohibited by default. |
| Trading frictions are first-class | Commission, spread, impact, latency, participation caps, lot size, and probabilistic partial fills affect portfolio accounting. |
| Reproducibility beats cleverness | Configurations, data fingerprints, code version, random seeds, and model artifacts are stored in each run manifest. |
| Discovery must be penalized | Candidate factors are evaluated through nested walk-forward validation with multiple-testing diagnostics and complexity penalties. |
| Uncertainty is reported | Results include bootstrap confidence intervals, regime slices, capacity stress, turnover, drawdown, and failure reasons. |
| Public and private data share one contract | CSV, Parquet, JSON, and yfinance adapters normalize into the same typed schema. |

## End-to-end flow

```text
Raw sources -> normalized bars/events -> point-in-time snapshots -> feature graph
      -> purged/embargoed splits -> candidate factor library -> cross-sectional model
      -> signal/target alignment -> execution simulator -> metrics and diagnostics
      -> run manifest + artifacts + human-readable report
```

## Time model

The core schema keeps these concepts separate:

- `event_at`: when a market observation or fundamental event occurred.
- `available_at`: the earliest timestamp at which the observation could reasonably have been known by the strategy.
- `decision_at`: when the strategy calculates a target position.
- `order_at`: when an order is submitted, after configured decision latency.
- `fill_at`: when the simulated fill occurs.

A feature may use only rows with `available_at <= decision_at - information_buffer`. A label may use prices after the decision timestamp and never contributes to a feature row. If `available_at` is missing for a non-price event, the ingestion layer rejects the record unless the user explicitly supplies a conservative lag policy.

## Data contracts

The normalized market data contract supports one row per instrument and bar:

| Column | Type | Meaning |
| --- | --- | --- |
| `symbol` | string | Stable instrument identifier. |
| `timestamp` | timezone-aware datetime | Bar/event timestamp in UTC. |
| `open`, `high`, `low`, `close` | float | Prices in source currency. |
| `adj_close` | float/null | Split/dividend-adjusted close when supplied by the source. |
| `volume` | float/null | Reported volume. |
| `currency` | string/null | Currency code. |
| `available_at` | timezone-aware datetime | Point-in-time usability timestamp. |
| `source` | string | Provider or file identifier. |
| `data_quality` | string | `ok`, `warn`, or `reject`. |

Fundamentals and alternative data use a long-form event contract with `symbol`, `field`, `value`, `event_at`, `available_at`, `source`, and `revision_id`. Revisions are retained rather than overwritten so point-in-time replay can use the vintage that existed at each decision date.

## Modeling layers

The factor layer contains deterministic transforms such as momentum, reversal, volatility, liquidity, quality, value, and residualized signals. Users can register custom factors through a small protocol. The adaptive discovery layer searches a bounded grammar of transforms and combinations, records every attempted candidate, and applies minimum breadth, turnover, stability, and multiple-testing controls. It does not claim to recreate any individual researcher; it provides inspectable, testable research machinery.

The default cross-sectional model is regularized linear ranking with optional elastic-net selection. A robust baseline is always evaluated alongside discovered models. Model selection is nested: inner walk-forward splits select hyperparameters and factors, while outer splits estimate performance. A candidate that only works on one split is marked unstable.

## Execution model

At each rebalance, the engine translates target weights into orders using prior holdings, prices, and available cash. Orders are delayed, capped by participation, and filled against a simulated range/volume model. Costs include commissions, bid-ask spread, nonlinear market impact, borrow/short fees, and optional dividends. Unfilled quantity remains open and is processed in later bars or expires under the chosen policy. Portfolio NAV is marked on a conservative basis and all assumptions are recorded.

## Verification gates

A run fails closed when any of the following occurs:

1. A feature reads a row with `available_at` after its decision time.
2. A label window overlaps the training period without the configured purge or embargo.
3. The universe contains only current survivors while historical membership is required.
4. A price series crosses an adjustment boundary without an explicit adjustment policy.
5. Execution assumptions are absent or unrealistically zero-cost for a non-trivial strategy.
6. The candidate count, search budget, or repeated experiments are not included in the selection penalty.
7. The output lacks an immutable data fingerprint and configuration manifest.

## Intended use

Inhibit produces research artifacts and simulated performance reports. It must not be interpreted as a promise of future returns. Before any live use, the operator would need independent data licensing review, broker/exchange integration review, operational controls, risk limits, monitoring, and a paper-trading period.
