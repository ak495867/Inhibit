from __future__ import annotations

import pandas as pd

from inhibit.features.engine import FeatureEngine
from inhibit.models.rules import MultiFactorCombinationRule


def three_day_range(frame: pd.DataFrame) -> pd.Series:
    range_pct = (frame["high"] - frame["low"]) / frame["close"]
    return (
        range_pct.groupby(frame["symbol"], sort=False)
        .rolling(3, min_periods=3)
        .mean()
        .reset_index(level=0, drop=True)
    )


if __name__ == "__main__":
    engine = FeatureEngine()
    engine.registry.register("three_day_range", three_day_range)
    rule = MultiFactorCombinationRule(
        name="range_adjusted_momentum",
        factors=("momentum_12_1", "three_day_range"),
        weights=(1.0, -0.25),
        normalize=True,
    )
    print("registered:", "three_day_range" in engine.registry.names())
    print("rule:", rule.name, rule.expression)
