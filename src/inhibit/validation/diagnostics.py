from __future__ import annotations

import pandas as pd

from inhibit.backtest.metrics import block_bootstrap_metric_interval


def regime_performance(
    equity: pd.DataFrame,
    n_bootstrap: int = 1000,
    seed: int = 42,
    block_length: int = 21,
) -> dict[str, dict[str, float]]:
    if equity.empty:
        return {}
    frame = equity.sort_values("timestamp").copy()
    frame["return"] = frame["equity"].pct_change()
    frame["realized_vol"] = frame["return"].rolling(21, min_periods=10).std()
    valid = frame.dropna(subset=["return", "realized_vol"])
    if len(valid) < 20:
        return {}
    valid["regime"] = pd.qcut(
        valid["realized_vol"], q=3, labels=["low_vol", "mid_vol", "high_vol"], duplicates="drop"
    )
    output: dict[str, dict[str, float]] = {}
    for regime, group in valid.groupby("regime", observed=True):
        returns = group["return"]
        low, high = block_bootstrap_metric_interval(
            returns, metric="sharpe", n_bootstrap=n_bootstrap, block_length=block_length, seed=seed
        )
        output[str(regime)] = {
            "observations": int(len(group)),
            "mean_return": float(returns.mean()),
            "sharpe_ci_low": low,
            "sharpe_ci_high": high,
        }
    return output
