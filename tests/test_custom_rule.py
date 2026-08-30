from __future__ import annotations

import numpy as np
import pandas as pd

from inhibit.models.discovery import AdaptiveFactorDiscovery
from inhibit.models.rules import MultiFactorCombinationRule
from inhibit.validation.splits import walk_forward_splits


def test_custom_multi_factor_rule_is_evaluated_and_selected() -> None:
    dates = pd.date_range("2021-01-01", periods=80, freq="B", tz="UTC")
    rows: list[dict[str, object]] = []
    for time_index, timestamp in enumerate(dates):
        for symbol_index in range(10):
            signal = symbol_index / 10
            noise = 0.45 * np.sin((time_index + symbol_index) / 2.0)
            factor_a = signal + noise
            factor_b = signal - noise
            rows.append(
                {
                    "timestamp": timestamp,
                    "symbol": f"S{symbol_index:02d}",
                    "factor_a": factor_a,
                    "factor_b": factor_b,
                    "forward_return": 0.5 * factor_a + 0.5 * factor_b,
                }
            )
    frame = pd.DataFrame(rows)
    splits = walk_forward_splits(frame["timestamp"], 30, 10, 10, 10, 2, 2)
    rule = MultiFactorCombinationRule(
        "custom_blend", ("factor_a", "factor_b"), (0.5, 0.5), normalize=False
    )
    result = AdaptiveFactorDiscovery(
        max_candidates=20, max_depth=1, complexity_penalty=0.0, custom_rules=[rule]
    ).discover(frame, ["factor_a", "factor_b"], splits)
    custom = next(
        candidate for candidate in result.candidates if candidate.name == "custom_blend"
    )
    assert custom.expression == "0.5*factor_a + 0.5*factor_b"
    assert custom.stability == 1.0
    assert custom.mean_rank_ic > 0.9
    assert "custom_blend" in result.selected_features
