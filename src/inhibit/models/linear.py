from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class ModelFit:
    feature_names: tuple[str, ...]
    coefficients: tuple[float, ...]
    intercept: float
    n_rows: int


class CrossSectionalRidge:
    def __init__(self, alpha: float = 10.0) -> None:
        self.alpha = alpha
        self._model: object | None = None
        self.feature_names: tuple[str, ...] = ()

    def fit(
        self,
        frame: pd.DataFrame,
        feature_names: list[str],
        label: str = "forward_return",
    ) -> ModelFit:
        usable = frame.dropna(subset=[*feature_names, label]).copy()
        if len(usable) < max(50, len(feature_names) * 10):
            raise ValueError("insufficient rows for factor model fit")
        x = usable[feature_names].to_numpy(dtype=float)
        y = usable[label].to_numpy(dtype=float)
        self._model = make_pipeline(StandardScaler(), Ridge(alpha=self.alpha))
        self._model.fit(x, y)
        ridge = self._model[-1]
        self.feature_names = tuple(feature_names)
        return ModelFit(
            self.feature_names,
            tuple(float(v) for v in ridge.coef_),
            float(ridge.intercept_),
            len(usable),
        )

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        if self._model is None:
            raise RuntimeError("fit the model before predict")
        result = pd.Series(np.nan, index=frame.index, dtype=float)
        usable = frame[list(self.feature_names)].notna().all(axis=1)
        if usable.any():
            matrix = frame.loc[usable, list(self.feature_names)].to_numpy(dtype=float)
            result.loc[usable] = self._model.predict(matrix)
        return result

    def score_to_weights(
        self,
        frame: pd.DataFrame,
        prediction: pd.Series,
        max_positions: int,
        max_weight: float,
    ) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for timestamp, group in frame.assign(prediction=prediction).groupby(
            "timestamp", sort=True
        ):
            group = group.dropna(subset=["prediction"])
            group = group.sort_values("prediction", ascending=False).head(max_positions)
            if group.empty:
                continue
            raw = group["prediction"].clip(lower=0.0)
            if raw.sum() <= 0:
                raw = pd.Series(1.0, index=group.index)
            weights = (raw / raw.sum()).clip(upper=max_weight)
            if weights.sum() > 0:
                weights = weights / weights.sum()
            for index, weight in weights.items():
                rows.append(
                    {
                        "timestamp": timestamp,
                        "symbol": group.loc[index, "symbol"],
                        "weight": float(weight),
                    }
                )
        return pd.DataFrame(rows, columns=["timestamp", "symbol", "weight"])
