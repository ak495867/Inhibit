from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_membership(path: str | Path) -> pd.DataFrame:
    membership = pd.read_csv(path)
    required = {"symbol", "effective_from", "effective_to"}
    missing = required - set(membership.columns)
    if missing:
        raise ValueError(f"membership file missing columns: {sorted(missing)}")
    membership["symbol"] = membership["symbol"].astype(str)
    membership["effective_from"] = pd.to_datetime(
        membership["effective_from"], utc=True
    )
    membership["effective_to"] = pd.to_datetime(membership["effective_to"], utc=True)
    if membership["effective_from"].isna().any():
        raise ValueError("membership effective_from contains invalid timestamps")
    if (
        membership["effective_to"].notna()
        & (membership["effective_to"] <= membership["effective_from"])
    ).any():
        raise ValueError(
            "membership intervals must have effective_to after effective_from"
        )
    for symbol, group in membership.sort_values(["symbol", "effective_from"]).groupby(
        "symbol"
    ):
        prior_to = group["effective_to"].shift(1)
        if ((prior_to.notna()) & (group["effective_from"] < prior_to)).any():
            raise ValueError(f"overlapping membership intervals for {symbol}")
    return membership


def apply_point_in_time_membership(
    frame: pd.DataFrame, membership: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, int]]:
    work = frame.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True)
    eligible = np.zeros(len(work), dtype=bool)
    interval_groups = {
        symbol: group.sort_values("effective_from")
        for symbol, group in membership.groupby("symbol", sort=False)
    }
    for symbol, positions in work.groupby("symbol", sort=False).groups.items():
        intervals = interval_groups.get(symbol)
        if intervals is None:
            continue
        timestamps = work.loc[positions, "timestamp"].to_numpy(dtype="datetime64[ns]")
        starts = intervals["effective_from"].to_numpy(dtype="datetime64[ns]")
        interval_index = starts.searchsorted(timestamps, side="right") - 1
        valid = interval_index >= 0
        if not valid.any():
            continue
        selected = intervals.iloc[np.maximum(interval_index, 0)]
        ends = selected["effective_to"].to_numpy(dtype="datetime64[ns]")
        active = valid & (pd.isna(ends) | (timestamps < ends))
        eligible[np.asarray(list(positions))[active]] = True
    filtered = work.loc[eligible].reset_index(drop=True)
    return filtered, {
        "membership_input_symbols": int(membership["symbol"].nunique()),
        "membership_eligible_symbols": int(filtered["symbol"].nunique()),
        "membership_removed_rows": int((~eligible).sum()),
    }
