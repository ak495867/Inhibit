from __future__ import annotations

import pandas as pd

from inhibit.config import UniverseConfig


def apply_universe_filters(
    frame: pd.DataFrame, config: UniverseConfig
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = frame.sort_values(["symbol", "timestamp"]).copy()
    work["dollar_volume"] = work["close"] * work["volume"]
    work["history_count_before"] = work.groupby("symbol", sort=False).cumcount()
    work["prior_close"] = work.groupby("symbol", sort=False)["close"].shift(1)
    work["prior_dollar_volume"] = work.groupby("symbol", sort=False)["dollar_volume"].shift(1)
    eligible = (
        (work["history_count_before"] >= config.min_history_bars)
        & (work["prior_close"] >= config.min_price)
        & (work["prior_dollar_volume"] >= config.min_dollar_volume)
    )
    input_symbols = int(work["symbol"].nunique())
    selected_symbols = set(work.loc[eligible, "symbol"])
    filtered = work.loc[eligible].drop(
        columns=["dollar_volume", "history_count_before", "prior_close", "prior_dollar_volume"]
    )
    return filtered.reset_index(drop=True), {
        "input_symbols": input_symbols,
        "eligible_symbols": int(len(selected_symbols)),
        "removed_symbols": int(input_symbols - len(selected_symbols)),
        "eligible_rows": int(eligible.sum()),
    }
