from __future__ import annotations

import pytest

from inhibit.config import (
    ExecutionConfig,
    FeatureConfig,
    InhibitConfig,
    PortfolioConfig,
    ScheduleConfig,
    ValidationConfig,
)


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (InhibitConfig(features=FeatureConfig(include=("momentum", "momentum"))), "duplicate"),
        (
            InhibitConfig(
                features=FeatureConfig(include=("momentum",)),
                schedule=ScheduleConfig(label_horizon_bars=0),
            ),
            "label_horizon",
        ),
        (
            InhibitConfig(
                features=FeatureConfig(include=("momentum",)),
                validation=ValidationConfig(holdout_fraction=1.0),
            ),
            "holdout_fraction",
        ),
        (
            InhibitConfig(
                features=FeatureConfig(include=("momentum",)),
                execution=ExecutionConfig(commission_bps=-1.0),
            ),
            "costs cannot be negative",
        ),
        (
            InhibitConfig(
                features=FeatureConfig(include=("momentum",)),
                portfolio=PortfolioConfig(max_turnover=-0.1),
            ),
            "cannot be negative",
        ),
        (
            InhibitConfig(
                features=FeatureConfig(include=("momentum",)),
                execution=ExecutionConfig(spread_bps=float("nan")),
            ),
            "finite number",
        ),
    ],
)
def test_invalid_config_values_fail_fast(config: InhibitConfig, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        config.validate()


def test_default_config_is_valid_with_a_baseline_feature() -> None:
    config = InhibitConfig(features=FeatureConfig(include=("momentum_12_1",)))
    config.validate()
