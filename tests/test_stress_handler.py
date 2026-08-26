from __future__ import annotations

import pandas as pd

from inhibit.backtest.execution import ExecutionSimulator
from inhibit.config import ExecutionConfig, PortfolioConfig


def high_volatility_bars() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-02", periods=6, freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "symbol": ["HV" for _ in timestamps],
            "timestamp": timestamps,
            "open": [100, 100, 120, 95, 125, 90],
            "high": [105, 125, 130, 135, 140, 120],
            "low": [95, 80, 90, 70, 85, 65],
            "close": [100, 120, 95, 125, 90, 110],
            "volume": [10_000 for _ in timestamps],
        }
    )


def test_high_volatility_handler_increases_slippage_and_reduces_participation() -> None:
    bars = high_volatility_bars()
    targets = pd.DataFrame(
        {"timestamp": [bars["timestamp"].iloc[0]], "symbol": ["HV"], "weight": [0.5]}
    )
    portfolio = PortfolioConfig(max_position_weight=1.0, max_turnover=1.0)
    default = ExecutionSimulator(ExecutionConfig(fill_probability=1.0), portfolio, seed=7).run(
        bars, targets
    )
    stress_config = ExecutionConfig(
        fill_probability=1.0,
        handler="high_volatility_stress",
        stress_volatility_threshold=0.001,
        stress_spread_multiplier=3.0,
        stress_impact_multiplier=4.0,
        stress_participation_multiplier=0.75,
        stress_fill_probability_floor=1.0,
    )
    stress = ExecutionSimulator(stress_config, portfolio, seed=7).run(bars, targets)
    default_fill = default.fills.loc[default.fills["reason"] == "filled"].iloc[0]
    stress_fill = stress.fills.loc[stress.fills["reason"] == "filled"].iloc[0]
    assert stress_fill["volatility_level"] > 0
    assert stress_fill["stress_factor"] > 0
    assert stress_fill["effective_spread_bps"] > default_fill["effective_spread_bps"]
    assert stress_fill["effective_impact_bps"] > default_fill["effective_impact_bps"]
    assert abs(stress_fill["filled_shares"]) < abs(default_fill["filled_shares"])


def test_tail_risk_handler_collapses_liquidity_and_widens_spread() -> None:
    bars = high_volatility_bars().copy()
    bars.loc[1, ["high", "low", "close"]] = [150.0, 50.0, 100.0]
    targets = pd.DataFrame(
        {"timestamp": [bars["timestamp"].iloc[0]], "symbol": ["HV"], "weight": [0.5]}
    )
    config = ExecutionConfig(
        fill_probability=1.0,
        handler="high_volatility_stress",
        stress_volatility_threshold=0.01,
        tail_risk_threshold=0.05,
        tail_spread_multiplier=8.0,
        tail_impact_multiplier=12.0,
        tail_liquidity_multiplier=0.95,
        tail_fill_probability_floor=1.0,
    )
    result = ExecutionSimulator(config, PortfolioConfig(max_position_weight=1.0), seed=7).run(
        bars, targets
    )
    fill = (
        result.fills.loc[result.fills["reason"] == "filled"]
        .sort_values("tail_risk_factor")
        .iloc[-1]
    )
    assert fill["tail_risk_factor"] > 0
    assert fill["liquidity_factor"] < 1
    assert fill["effective_spread_bps"] > config.spread_bps
    assert fill["effective_impact_bps"] > config.impact_bps
    assert fill["effective_participation_rate"] < config.participation_rate
