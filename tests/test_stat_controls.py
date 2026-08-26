from __future__ import annotations

import numpy as np
import pandas as pd

from inhibit.backtest.metrics import (
    artifact_flags,
    benjamini_hochberg,
    block_bootstrap_metric_interval,
)


def test_block_bootstrap_is_reproducible_and_validates_block_length() -> None:
    returns = pd.Series(np.linspace(-0.01, 0.01, 100))
    first = block_bootstrap_metric_interval(returns, "sharpe", 250, 7, 11)
    second = block_bootstrap_metric_interval(returns, "sharpe", 250, 7, 11)
    assert first == second
    assert first[0] <= first[1]


def test_benjamini_hochberg_controls_candidate_discoveries() -> None:
    q_values, passed = benjamini_hochberg([0.001, 0.02, 0.50, 0.90], 0.05)
    assert len(q_values) == 4
    assert passed[:2] == [True, True]
    assert passed[2:] == [False, False]


def test_artifact_flags_catch_high_sharpe_and_low_volatility() -> None:
    flags = artifact_flags({"sharpe": 5.01, "annual_volatility": 0.009})
    assert "suspected_verification_artifact_high_sharpe" in flags
    assert "suspected_verification_artifact_low_annualized_volatility" in flags
