from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MultiFactorCombinationRule:
    name: str
    factors: tuple[str, ...]
    weights: tuple[float, ...]
    normalize: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.isidentifier():
            raise ValueError("rule name must be a non-empty Python identifier")
        if len(self.factors) < 2:
            raise ValueError("a combination rule requires at least two factors")
        if len(self.factors) != len(self.weights):
            raise ValueError("factors and weights must have the same length")
        if len(set(self.factors)) != len(self.factors):
            raise ValueError("combination factors must be unique")
        if not any(float(weight) != 0 for weight in self.weights):
            raise ValueError("at least one combination weight must be non-zero")

    @property
    def expression(self) -> str:
        terms = [
            f"{weight:g}*{factor}"
            for factor, weight in zip(self.factors, self.weights, strict=True)
        ]
        return " + ".join(terms)

    @property
    def complexity(self) -> int:
        return len(self.factors) + 1

    def evaluate(self, frame: pd.DataFrame) -> pd.Series:
        missing = sorted(set(self.factors) - set(frame.columns))
        if missing:
            raise ValueError(f"custom rule {self.name!r} missing factors: {missing}")
        values = frame[list(self.factors)].astype(float).replace([np.inf, -np.inf], np.nan)
        if self.normalize:
            for factor in self.factors:
                values[factor] = (
                    values[factor].groupby(frame["timestamp"], sort=False).transform(self._zscore)
                )
        result = sum(
            values[factor] * weight
            for factor, weight in zip(self.factors, self.weights, strict=True)
        )
        return result.replace([np.inf, -np.inf], np.nan).rename(self.name)

    @staticmethod
    def _zscore(group: pd.Series) -> pd.Series:
        valid = group.dropna()
        if valid.empty:
            return group
        deviation = valid.std(ddof=0)
        if deviation == 0 or pd.isna(deviation):
            return group.where(group.isna(), 0.0)
        return (group - valid.mean()) / deviation
