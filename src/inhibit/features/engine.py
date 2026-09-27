from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from inhibit.features.builtins import BUILTIN_FACTORS

FactorFunction = Callable[[pd.DataFrame], pd.Series]


class LeakageError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureAudit:
    feature_columns: tuple[str, ...]
    rows: int
    finite_values: int
    availability_violations: int
    future_price_violations: int

    @property
    def passed(self) -> bool:
        return self.availability_violations == 0 and self.future_price_violations == 0


class FeatureRegistry:
    def __init__(self) -> None:
        self._functions: dict[str, FactorFunction] = dict(BUILTIN_FACTORS)

    def register(self, name: str, function: FactorFunction) -> None:
        if not name or name in self._functions:
            raise ValueError(f"factor name is empty or already registered: {name!r}")
        self._functions[name] = function

    def get(self, name: str) -> FactorFunction:
        if name not in self._functions:
            raise KeyError(f"unknown factor: {name}")
        return self._functions[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._functions))


class FeatureEngine:
    def __init__(self, registry: FeatureRegistry | None = None) -> None:
        self.registry = registry or FeatureRegistry()

    def build(
        self,
        prices: pd.DataFrame,
        factors: Iterable[str],
        information_buffer_bars: int = 1,
        winsorize_quantiles: tuple[float, float] = (0.01, 0.99),
        standardize_cross_section: bool = True,
    ) -> tuple[pd.DataFrame, FeatureAudit]:
        frame = (
            prices.sort_values(["symbol", "timestamp"]).reset_index(drop=True).copy()
        )
        if "available_at" not in frame:
            raise LeakageError("available_at is required for feature generation")
        if information_buffer_bars < 0:
            raise ValueError("information_buffer_bars cannot be negative")
        factor_names = tuple(factors)
        if not factor_names:
            raise ValueError("at least one factor is required")
        for name in factor_names:
            values = self.registry.get(name)(frame)
            if not isinstance(values, pd.Series):
                values = pd.Series(values, index=frame.index)
            frame[name] = values.astype(float)
        for name in factor_names:
            frame[name] = self._cross_section_transform(
                frame, name, winsorize_quantiles, standardize_cross_section
            )
            if information_buffer_bars:
                frame[name] = frame.groupby("symbol", sort=False)[name].shift(
                    information_buffer_bars
                )
        source_available = frame.groupby("symbol", sort=False)["available_at"].shift(
            information_buffer_bars or 0
        )
        availability_violations = int(
            (source_available > frame["timestamp"]).fillna(False).sum()
        )
        finite_values = int(
            np.isfinite(frame[list(factor_names)].to_numpy(dtype=float)).sum()
        )
        future_price_violations = self._future_price_violations(
            frame, factor_names, source_available
        )
        audit = FeatureAudit(
            factor_names,
            len(frame),
            finite_values,
            availability_violations,
            future_price_violations,
        )
        if not audit.passed:
            raise LeakageError(
                "feature audit failed: "
                f"availability={availability_violations}, future_price={future_price_violations}"
            )
        return frame, audit

    @staticmethod
    def _cross_section_transform(
        frame: pd.DataFrame,
        name: str,
        quantiles: tuple[float, float],
        standardize: bool,
    ) -> pd.Series:
        low, high = quantiles
        if not 0 <= low < high <= 1:
            raise ValueError("winsorize quantiles must satisfy 0 <= low < high <= 1")
        values = frame[name].replace([np.inf, -np.inf], np.nan)
        clipped = values.groupby(frame["timestamp"], sort=False).transform(
            lambda group: group.clip(group.quantile(low), group.quantile(high))
        )
        if not standardize:
            return clipped

        def standardize(group: pd.Series) -> pd.Series:
            finite = group.dropna()
            if finite.empty:
                return group
            deviation = finite.std(ddof=0)
            if deviation == 0 or pd.isna(deviation):
                return group.where(group.isna(), 0.0)
            return (group - finite.mean()) / deviation

        return clipped.groupby(frame["timestamp"], sort=False).transform(standardize)

    @staticmethod
    def _future_price_violations(
        frame: pd.DataFrame, factor_names: Iterable[str], source_available: pd.Series
    ) -> int:
        violations = 0
        for name in factor_names:
            values = frame[name].notna() & source_available.notna()
            if values.any():
                violations += int(
                    (
                        source_available.loc[values] > frame.loc[values, "timestamp"]
                    ).sum()
                )
        return violations


def add_forward_return_label(frame: pd.DataFrame, horizon_bars: int) -> pd.DataFrame:
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be positive")
    result = frame.sort_values(["symbol", "timestamp"]).copy()
    future_close = result.groupby("symbol", sort=False)["close"].shift(-horizon_bars)
    result["forward_return"] = future_close / result["close"] - 1.0
    result["label_at"] = result.groupby("symbol", sort=False)["timestamp"].shift(
        -horizon_bars
    )
    return result
