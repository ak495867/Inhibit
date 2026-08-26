# Inhibit Methodology

## Research claims

Inhibit does not define “edge” as a high historical Sharpe ratio. A candidate is only promoted when it improves on a simple baseline across multiple chronological test windows, remains directionally stable, survives realistic friction assumptions, and has enough breadth and capacity to be economically meaningful. A failed test is a useful result: the run records why a candidate was rejected rather than silently removing it.

## Leakage controls

The engine uses four safeguards together. First, every row has an `available_at` timestamp. Second, factor functions use lagged observations and the feature engine applies an additional information buffer. Third, labels are forward returns and are never used before their horizon has elapsed. Fourth, walk-forward splits maintain separate train, validation, test, purge, and embargo regions.

| Risk | Inhibit control |
| --- | --- |
| Same-bar close leakage | Default execution delay is one bar; factors are lagged before a decision. |
| Restated fundamentals | Event schema retains `revision_id` and requires `available_at` for non-price data. |
| Overlapping labels | Forward horizons are purged from neighboring training regions. |
| Repeated search overfitting | Candidate count and complexity are recorded; rank-IC is penalized and stability is required. |
| Survivorship bias | Historical universe membership is a required extension point rather than silently inferred from current symbols. |
| Corporate-action mismatch | `adj_close` is retained separately and the source adjustment policy is part of the run assumptions. |
| Unrealistic fills | Participation limits, partial fills, probabilistic rejection, spread, commission, nonlinear impact, and borrow fees are explicit. |

## Factor discovery

The built-in discovery engine searches a bounded grammar over user-selected primitive factors. It evaluates primitive factors and pairwise additive, subtractive, and multiplicative combinations on chronological validation windows. The search is intentionally limited: unbounded symbolic regression will almost always find attractive historical noise when the research budget is large enough.

For each candidate, Inhibit records the expression, complexity, mean rank information coefficient, median rank information coefficient, number of observations, and the share of windows with positive rank information coefficient. A candidate is selected only when it beats the baseline after the complexity penalty and meets the configured stability threshold. Production extensions can add genetic programming or Bayesian search, but they must preserve the same run ledger and outer holdout discipline.

## Portfolio construction

Predictions are converted into non-negative cross-sectional weights by ranking positive scores, limiting the number of positions, and clipping each position to a maximum weight. Rebalances are then constrained by a daily turnover cap. In long-short extensions, the same pipeline should add dollar neutrality, sector neutrality, borrow availability, locate costs, and explicit short-sale constraints rather than simply allowing negative weights.

## Execution accounting

For each order, the simulator records requested shares, filled shares, execution price, notional, commission, spread cost, impact cost, total cost, and the reason for any unfilled quantity. The default impact rate scales with the order’s participation rate using a configurable exponent. An order that is only partially filled leaves a residual target, which creates rebalancing pressure at later bars. Borrow fees accrue daily on short notional.

## Robustness protocol

A credible research run should be repeated with alternative lookbacks, universe definitions, rebalance frequencies, friction multipliers, and untouched holdout periods. Review should include the full distribution of window returns, maximum drawdown, turnover, fill ratio, exposure concentration, factor correlation, and performance by volatility or liquidity regime. The output of Inhibit is evidence for or against a hypothesis, not an automated trading instruction.
