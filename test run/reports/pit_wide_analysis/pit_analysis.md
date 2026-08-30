# Point-in-Time Universe and Statistical-Control Analysis

The current-constituent Sharpe was **0.655887**; the point-in-time-membership approximation Sharpe was **0.328563**. The change is **-0.327324**.

## FDR by complexity threshold

|   complexity_threshold |   candidate_count |   rejections |   rejection_rate |    fdr_q |
|-----------------------:|------------------:|-------------:|-----------------:|---------:|
|               1.000000 |          4.000000 |     0.000000 |         0.000000 | 0.050000 |
|               2.000000 |         44.000000 |     0.000000 |         0.000000 | 0.050000 |
|               3.000000 |         52.000000 |     0.000000 |         0.000000 | 0.050000 |

## Bootstrap and walk-forward plots

The PIT run’s block-bootstrap Sharpe interval is **[-0.199568, 1.207308]** using 2,000 21-bar circular block resamples. The plots are `pit_block_bootstrap_sharpe.png` and `pit_walk_forward_stability.png`; the underlying tables are `fdr_complexity_summary.csv` and `walk_forward_top5.csv`.

The PIT membership file is reconstructed from a free public dated-change table and is therefore an approximation, not an official licensed index-vintage feed. The comparison reduces terminal-constituent survivorship bias but does not remove all data-quality, delisting, ticker-history, or membership-timing risks.
