from __future__ import annotations

from math import erfc, sqrt

import numpy as np
import pandas as pd


def performance_metrics(
    equity: pd.DataFrame, fills: pd.DataFrame | None = None, periods_per_year: int = 252
) -> dict[str, float]:
    if equity.empty:
        return {
            "annual_return": float("nan"),
            "annual_volatility": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown": float("nan"),
            "turnover": float("nan"),
            "fill_ratio": float("nan"),
        }
    series = equity.sort_values("timestamp").set_index("timestamp")["equity"].astype(float)
    returns = series.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    years = max(len(returns) / periods_per_year, 1 / periods_per_year)
    annual_return = (
        (series.iloc[-1] / series.iloc[0]) ** (1 / years) - 1
        if series.iloc[0] > 0
        else float("nan")
    )
    annual_vol = (
        returns.std(ddof=1) * np.sqrt(periods_per_year) if len(returns) > 1 else float("nan")
    )
    sharpe = annual_return / annual_vol if annual_vol and np.isfinite(annual_vol) else float("nan")
    drawdown = series / series.cummax() - 1
    turnover = 0.0
    fill_ratio = float("nan")
    if fills is not None and not fills.empty:
        turnover = float(
            fills["notional"].sum() / max(series.mean(), 1e-12) / max(years, 1 / periods_per_year)
        )
        requested = fills["requested_shares"].abs().sum()
        filled = fills["filled_shares"].abs().sum()
        fill_ratio = float(filled / requested) if requested else float("nan")
    return {
        "annual_return": float(annual_return),
        "annual_volatility": float(annual_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "turnover": turnover,
        "fill_ratio": fill_ratio,
        "ending_equity": float(series.iloc[-1]),
    }


def block_bootstrap_metric_interval(
    returns: pd.Series,
    metric: str = "mean",
    n_bootstrap: int = 1000,
    block_length: int = 21,
    seed: int = 42,
) -> tuple[float, float]:
    values = pd.Series(returns).dropna().to_numpy(dtype=float)
    if len(values) < 20:
        return float("nan"), float("nan")
    if block_length < 1:
        raise ValueError("block_length must be positive")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(values) / block_length))
    starts = rng.integers(0, len(values), size=(n_bootstrap, n_blocks))
    offsets = np.arange(block_length)
    indices = (starts[:, :, None] + offsets[None, None, :]) % len(values)
    sampled = values[indices].reshape(n_bootstrap, -1)[:, : len(values)]
    if metric == "mean":
        stats = sampled.mean(axis=1)
    elif metric == "sharpe":
        stats = sampled.mean(axis=1) / np.maximum(sampled.std(axis=1, ddof=1), 1e-12) * np.sqrt(252)
    else:
        raise ValueError(f"unknown bootstrap metric: {metric}")
    return tuple(float(value) for value in np.quantile(stats, [0.025, 0.975]))


def bootstrap_metric_interval(
    returns: pd.Series, metric: str = "mean", n_bootstrap: int = 1000, seed: int = 42
) -> tuple[float, float]:
    return block_bootstrap_metric_interval(returns, metric, n_bootstrap, 1, seed)


def one_sided_normal_p_value(scores: list[float]) -> float:
    if not scores:
        return 1.0
    mean = float(np.mean(scores))
    deviation = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    if deviation == 0:
        return 0.0 if mean > 0 else 1.0
    statistic = mean / (deviation / np.sqrt(len(scores)))
    return float(0.5 * erfc(statistic / sqrt(2)))


def benjamini_hochberg(p_values: list[float], fdr_q: float) -> tuple[list[float], list[bool]]:
    if not 0 < fdr_q <= 1:
        raise ValueError("fdr_q must be in (0, 1]")
    count = len(p_values)
    if count == 0:
        return [], []
    order = np.argsort(np.asarray(p_values, dtype=float))
    q_values = np.ones(count, dtype=float)
    running = 1.0
    for rank in range(count, 0, -1):
        index = int(order[rank - 1])
        running = min(running, float(p_values[index]) * count / rank)
        q_values[index] = running
    passed = [bool(value <= fdr_q) for value in q_values]
    return q_values.tolist(), passed


def artifact_flags(
    metrics: dict[str, float],
    sharpe_threshold: float = 5.0,
    volatility_floor: float = 0.01,
) -> list[str]:
    flags: list[str] = []
    sharpe = metrics.get("sharpe", float("nan"))
    volatility = metrics.get("annual_volatility", float("nan"))
    if np.isfinite(sharpe) and sharpe > sharpe_threshold:
        flags.append("suspected_verification_artifact_high_sharpe")
    if np.isfinite(volatility) and volatility < volatility_floor:
        flags.append("suspected_verification_artifact_low_annualized_volatility")
    return flags
