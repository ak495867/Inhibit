from __future__ import annotations

import numpy as np
import pandas as pd

from inhibit.config import (
    ExecutionConfig,
    FeatureConfig,
    InhibitConfig,
    ScheduleConfig,
    ValidationConfig,
)
from inhibit.data.schema import normalize_prices
from inhibit.research import ResearchRunner


def make_prices(n_days: int = 1100, n_symbols: int = 25) -> pd.DataFrame:
    dates = pd.date_range("2017-01-01", periods=n_days, freq="B", tz="UTC")
    rows: list[dict[str, object]] = []
    for symbol_id in range(n_symbols):
        symbol = f"S{symbol_id:02d}"
        base = 20 + symbol_id
        returns = 0.0001 + 0.001 * np.sin(np.arange(n_days) / (17 + symbol_id))
        prices = base * np.exp(np.cumsum(returns))
        for date, price in zip(dates, prices, strict=True):
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp": date,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 500_000,
                    "available_at": date,
                }
            )
    return normalize_prices(pd.DataFrame(rows), source="runner-test")


def test_end_to_end_run(tmp_path) -> None:
    prices = make_prices()
    input_path = tmp_path / "prices.csv"
    prices.to_csv(input_path, index=False)
    config = InhibitConfig(
        name="test",
        features=FeatureConfig(
            include=("momentum_12_1", "reversal_1", "volatility_63"),
            discovery={
                "max_candidates": 10,
                "max_depth": 2,
                "custom_rules": [
                    {
                        "name": "momentum_reversal_blend",
                        "factors": ["momentum_12_1", "reversal_1"],
                        "weights": [0.7, -0.3],
                        "normalize": True,
                    }
                ],
            },
        ),
        validation=ValidationConfig(
            train_bars=500,
            validation_bars=100,
            test_bars=100,
            step_bars=100,
            embargo_bars=10,
            n_bootstrap=100,
            min_test_periods=2,
        ),
        schedule=ScheduleConfig(
            execution_delay_bars=1, information_buffer_bars=1, label_horizon_bars=10
        ),
        execution=ExecutionConfig(commission_bps=1, spread_bps=3, impact_bps=5),
    )
    manifest = ResearchRunner(config).run(prices, input_path, tmp_path / "run")
    assert manifest["split_count"] >= 2
    assert (tmp_path / "run" / "manifest.json").exists()
    assert (tmp_path / "run" / "equity.csv").exists()
    assert set(manifest["metrics"]) >= {"annual_return", "sharpe", "max_drawdown"}
    assert manifest["custom_rules"][0]["name"] == "momentum_reversal_blend"
    assert "manifest.json" not in manifest["artifacts"]
    assert "equity.csv" in manifest["artifacts"]
