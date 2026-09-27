from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class WalkForwardSplit:
    split_id: int
    train: np.ndarray
    validation: np.ndarray
    test: np.ndarray
    purged: np.ndarray
    embargoed: np.ndarray


class SplitError(ValueError):
    pass


def walk_forward_splits(
    timestamps: pd.Series | pd.Index,
    train_bars: int,
    validation_bars: int,
    test_bars: int,
    step_bars: int,
    embargo_bars: int,
    label_horizon_bars: int,
) -> list[WalkForwardSplit]:
    raw_timestamps = pd.Series(timestamps).reset_index(drop=True)
    unique_times = pd.Index(
        pd.to_datetime(raw_timestamps.drop_duplicates(), utc=True).sort_values()
    )
    if min(train_bars, validation_bars, test_bars, step_bars) < 1:
        raise SplitError("split lengths must be positive")
    if min(embargo_bars, label_horizon_bars) < 0:
        raise SplitError("embargo and label horizon cannot be negative")
    splits: list[WalkForwardSplit] = []
    split_id = 0
    train_end = train_bars
    while True:
        purge_start = train_end
        validation_start = purge_start + label_horizon_bars
        validation_end = validation_start + validation_bars
        embargo_start = validation_end
        test_start = embargo_start + embargo_bars
        test_end = test_start + test_bars
        if test_end > len(unique_times):
            break
        train_times = unique_times[:train_end]
        purged_times = unique_times[purge_start:validation_start]
        validation_times = unique_times[validation_start:validation_end]
        embargoed_times = unique_times[embargo_start:test_start]
        test_times = unique_times[test_start:test_end]
        splits.append(
            WalkForwardSplit(
                split_id=split_id,
                train=np.flatnonzero(raw_timestamps.isin(train_times).to_numpy()),
                validation=np.flatnonzero(raw_timestamps.isin(validation_times).to_numpy()),
                test=np.flatnonzero(raw_timestamps.isin(test_times).to_numpy()),
                purged=np.flatnonzero(raw_timestamps.isin(purged_times).to_numpy()),
                embargoed=np.flatnonzero(raw_timestamps.isin(embargoed_times).to_numpy()),
            )
        )
        split_id += 1
        train_end += step_bars
    if not splits:
        raise SplitError("not enough chronological data for one walk-forward split")
    return splits


def assert_no_overlap(split: WalkForwardSplit) -> None:
    groups = {
        "train": set(split.train),
        "validation": set(split.validation),
        "test": set(split.test),
        "purged": set(split.purged),
        "embargoed": set(split.embargoed),
    }
    for left, right in (
        ("train", "validation"),
        ("train", "test"),
        ("validation", "test"),
        ("train", "purged"),
        ("validation", "embargoed"),
        ("test", "embargoed"),
    ):
        if groups[left] & groups[right]:
            raise SplitError(f"split {split.split_id} overlaps {left} and {right}")
