# CI and Point-in-Time Verification Results

This report records the local checks completed for the Inhibit release containing the GitHub Actions workflow.

## Local CI-equivalent checks

| Check | Result |
| --- | --- |
| `ruff format --check .` | Passed |
| `ruff check .` | Passed |
| `PYTHONPATH=src pytest -q` | Passed: 13 tests |
| `inhibit verify --run runs/real_sp500_pit --input data/sp500_yfinance_2015_2026_clean.csv` | Passed |
| `inhibit verify --run runs/real_sp500_pit_wide --input data/sp500_yfinance_2015_2026_clean.csv` | Passed |

The current GitHub workflow runs dependency checks, formatting, linting, tests, and installed-CLI smoke checks on Python 3.11, 3.12, and 3.13. Each matrix leg publishes a JUnit XML test-results artifact, including on failure when a report file is produced. The point-in-time metrics below remain a historical snapshot from the release noted above.

## Point-in-time validation snapshot

The current-constituent run produced an out-of-sample Sharpe of 0.655887. The point-in-time membership approximation produced 0.328563, a difference of -0.327324. The PIT run used 13 walk-forward windows, annualized volatility of 0.377110, maximum drawdown of -0.482842, and a 1,000-resample manifest Sharpe interval of [-0.172297, 1.219269].

The wider PIT symbolic search evaluated 52 candidates. Benjamini–Hochberg FDR rejections were zero at maximum symbolic complexity thresholds 1, 2, and 3. The 2,000-resample diagnostic block-bootstrap interval was [-0.199568, 1.207308].

The membership file is reconstructed from free public dated-change information. It reduces terminal-constituent survivorship bias but does not fully eliminate risks from ticker changes, delistings, historical data revisions, incomplete membership timing, or licensed index-vintage differences.

These are research validation results, not investment advice or evidence of guaranteed future performance.
