# Wide-Search Top-Five Factor Analysis

> Selection is based on validation metrics. Held-out test metrics are reported after the selection ranking and must not be used to choose a factor.

The manifest baseline rank IC is **0.850005**. The wide search evaluated **131** candidates across **4** chronological windows. The table below contains the top five candidates ranked by validation mean rank IC after the configured complexity penalty.

|   validation_rank | name                                                 |   complexity |   mean_rank_ic |   median_rank_ic |   stability |   mean_test_rank_ic |   median_test_rank_ic |   test_stability |   test_observations | selected   |
|------------------:|:-----------------------------------------------------|-------------:|---------------:|-----------------:|------------:|--------------------:|----------------------:|-----------------:|--------------------:|:-----------|
|                 1 | reversal_1                                           |            1 |       0.954890 |         0.959598 |    1.000000 |            0.959421 |              0.959212 |         1.000000 |               12575 | True       |
|                 2 | reversal_1_plus_dollar_volume_21                     |            2 |       0.939236 |         0.947850 |    1.000000 |            0.947812 |              0.947784 |         1.000000 |               12575 | False      |
|                 3 | momentum_12_1_plus_reversal_1_minus_dollar_volume_21 |            3 |       0.933136 |         0.945831 |    1.000000 |            0.945540 |              0.945711 |         1.000000 |               12575 | False      |
|                 4 | momentum_12_1_plus_reversal_1                        |            2 |       0.931016 |         0.939702 |    1.000000 |            0.939590 |              0.939358 |         1.000000 |               12575 | False      |
|                 5 | momentum_12_1_plus_reversal_1_minus_volatility_63    |            3 |       0.886229 |         0.898721 |    1.000000 |            0.898188 |              0.898259 |         1.000000 |               12575 | False      |

## Interpretation

**reversal_1** has validation mean rank IC 0.954890 and validation stability 1.00. On the held-out windows its mean rank IC is 0.959421, median rank IC is 0.959212, and positive-window stability is 1.00; the held-out result is therefore positive.

**reversal_1_plus_dollar_volume_21** has validation mean rank IC 0.939236 and validation stability 1.00. On the held-out windows its mean rank IC is 0.947812, median rank IC is 0.947784, and positive-window stability is 1.00; the held-out result is therefore positive.

**momentum_12_1_plus_reversal_1_minus_dollar_volume_21** has validation mean rank IC 0.933136 and validation stability 1.00. On the held-out windows its mean rank IC is 0.945540, median rank IC is 0.945711, and positive-window stability is 1.00; the held-out result is therefore positive.

**momentum_12_1_plus_reversal_1** has validation mean rank IC 0.931016 and validation stability 1.00. On the held-out windows its mean rank IC is 0.939590, median rank IC is 0.939358, and positive-window stability is 1.00; the held-out result is therefore positive.

**momentum_12_1_plus_reversal_1_minus_volatility_63** has validation mean rank IC 0.886229 and validation stability 1.00. On the held-out windows its mean rank IC is 0.898188, median rank IC is 0.898259, and positive-window stability is 1.00; the held-out result is therefore positive.

## Limitations

Rank IC is a cross-sectional association statistic, not a net portfolio return. It does not include trading costs, capacity, turnover, or fill behavior. The candidate ledger uses the validation set for ranking and the test set only for post-selection reporting in this analysis. The current verification dataset is deterministic and smooth, so its unusually strong IC and stability values are pipeline checks rather than evidence of a persistent market edge.

The full run manifest, candidate ledger, execution fills, and verification command should be retained together for auditability.
