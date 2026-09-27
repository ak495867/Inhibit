from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from inhibit.backtest.execution import ExecutionSimulator
from inhibit.cli.main import main
from inhibit.config import ExecutionConfig, PortfolioConfig
from inhibit.data.schema import DataContractError, normalize_prices
from inhibit.features.engine import FeatureEngine, LeakageError
from inhibit.validation.splits import assert_no_overlap, walk_forward_splits


def price_fixture(
    n_days: int = 320, symbols: tuple[str, ...] = ("AAA", "BBB", "CCC")
) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B", tz="UTC")
    rows: list[dict[str, object]] = []
    for index, symbol in enumerate(symbols):
        prices = 50 + index + np.cumsum(np.full(n_days, 0.05 + index * 0.01))
        for date, price in zip(dates, prices, strict=True):
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp": date,
                    "open": price,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price,
                    "volume": 100_000,
                    "available_at": date,
                }
            )
    return normalize_prices(pd.DataFrame(rows), source="test")


def test_schema_rejects_missing_columns() -> None:
    with pytest.raises(DataContractError):
        normalize_prices(pd.DataFrame({"symbol": ["AAA"], "timestamp": ["2020-01-01"]}))


def test_schema_rejects_non_finite_market_values() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "timestamp": ["2020-01-01"],
            "open": [1.0],
            "high": [float("inf")],
            "low": [1.0],
            "close": [1.0],
            "volume": [1.0],
        }
    )
    with pytest.raises(DataContractError, match="finite"):
        normalize_prices(frame)


def test_validate_config_command_accepts_valid_yaml(tmp_path, capsys) -> None:
    config_path = tmp_path / "config.yml"
    config_path.write_text("features:\n  include: [momentum_12_1]\n")
    assert main(["validate-config", "--config", str(config_path)]) == 0
    assert '"valid": true' in capsys.readouterr().out


def test_yfinance_export_creates_parent_directories(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "inhibit.cli.main.load_yfinance",
        lambda *args, **kwargs: pd.DataFrame({"symbol": ["AAA"]}),
    )
    output = tmp_path / "nested" / "data.csv"
    assert (
        main(
            [
                "fetch-yfinance",
                "--symbols",
                "AAA",
                "--start",
                "2024-01-01",
                "--end",
                "2024-02-01",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert output.exists()


def test_feature_engine_lags_and_audits() -> None:
    frame, audit = FeatureEngine().build(price_fixture(), ["reversal_1"], information_buffer_bars=1)
    assert audit.passed
    assert frame["reversal_1"].iloc[:3].isna().all()


def test_feature_engine_rejects_future_availability() -> None:
    frame = price_fixture()
    frame["available_at"] = frame["timestamp"] + pd.Timedelta(days=2)
    with pytest.raises(LeakageError):
        FeatureEngine().build(frame, ["reversal_1"], information_buffer_bars=1)


def test_walk_forward_splits_are_disjoint() -> None:
    timestamps = pd.Series(pd.date_range("2020-01-01", periods=1000, freq="B", tz="UTC"))
    splits = walk_forward_splits(timestamps, 500, 100, 100, 100, 20, 10)
    assert len(splits) == 3
    for split in splits:
        assert_no_overlap(split)


def test_execution_models_partial_fills_and_costs() -> None:
    bars = price_fixture(3, ("AAA",))
    targets = pd.DataFrame(
        {"timestamp": [bars["timestamp"].iloc[0]], "symbol": ["AAA"], "weight": [0.5]}
    )
    result = ExecutionSimulator(
        ExecutionConfig(
            participation_rate=0.01,
            fill_probability=1.0,
            commission_bps=1,
            spread_bps=5,
            impact_bps=10,
        ),
        PortfolioConfig(max_position_weight=1.0),
        seed=1,
    ).run(bars, targets)
    assert not result.equity.empty
    assert result.fills["filled_shares"].iloc[0] < result.fills["requested_shares"].iloc[0]
    assert result.fills["total_cost"].iloc[0] > 0
