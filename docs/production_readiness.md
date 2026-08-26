# Production Readiness

Inhibit is production-oriented research infrastructure. It is not yet a live capital deployment system, and the distinction is deliberate. The research layer is fail-closed and reproducible; live execution requires external controls that cannot be safely inferred from historical bars.

## Included in the repository

| Control | Status |
| --- | --- |
| Typed configuration and conservative non-zero-cost defaults | Implemented |
| CSV, JSON/NDJSON, Parquet, and optional yfinance ingestion | Implemented |
| Point-in-time availability timestamps and lagged factor generation | Implemented |
| Point-in-time universe warm-up and prior-liquidity checks | Implemented |
| Purged and embargoed chronological walk-forward splits | Implemented |
| Minimum test-window enforcement | Implemented |
| Bounded adaptive factor search and custom multi-factor rules | Implemented |
| Commission, spread, impact, participation, probabilistic fills, latency, turnover caps, lot sizes, borrow fees, and order expiry | Implemented |
| Run manifests with configuration, data, runtime, artifact, and metric fingerprints | Implemented |
| Manifest and artifact verification CLI | Implemented |
| Automated tests and linting | Implemented |

## Required before live deployment

A live deployment would still need licensed point-in-time data with historical universe membership, a broker or exchange adapter, durable order and fill state, reconciliation, idempotency keys, kill switches, exposure and loss limits, borrow and locate availability, market-hours and holiday calendars, clock synchronization, secrets management, alerting, audit retention, paper-trading evidence, and independent code and risk review.

These are not placeholders hidden behind the research CLI. They are separate production systems because a historical simulator cannot prove that a broker acknowledged an order, that a position was reconciled, or that an operator can stop a runaway process.

## Release gate

A candidate release should be frozen to a commit, run on an untouched holdout, archived with its input fingerprint and manifest, reviewed for data adjustments and universe membership, stress-tested under multiplied friction assumptions, and observed in paper trading. A high simulated Sharpe from a deterministic or highly smoothed fixture is a test of pipeline wiring, not evidence of a tradable edge.
