from __future__ import annotations

import numpy as np
import pandas as pd


def _group_shift(frame: pd.DataFrame, series: pd.Series, periods: int = 1) -> pd.Series:
    return series.groupby(frame["symbol"], sort=False).shift(periods)


def momentum_12_1(frame: pd.DataFrame) -> pd.Series:
    close = frame["close"]
    lag_21 = _group_shift(frame, close, 21)
    lag_252 = _group_shift(frame, close, 252)
    return lag_21 / lag_252 - 1.0


def reversal_1(frame: pd.DataFrame) -> pd.Series:
    previous = _group_shift(frame, frame["close"], 1)
    two_back = _group_shift(frame, frame["close"], 2)
    return previous / two_back - 1.0


def volatility_63(frame: pd.DataFrame) -> pd.Series:
    returns = frame.groupby("symbol", sort=False)["close"].pct_change()
    lagged = _group_shift(frame, returns, 1)
    return (
        lagged.groupby(frame["symbol"], sort=False)
        .rolling(63, min_periods=42)
        .std()
        .reset_index(level=0, drop=True)
    )


def dollar_volume_21(frame: pd.DataFrame) -> pd.Series:
    dollar_volume = frame["close"] * frame["volume"]
    lagged = _group_shift(frame, dollar_volume, 1)
    return np.log1p(
        lagged.groupby(frame["symbol"], sort=False)
        .rolling(21, min_periods=10)
        .mean()
        .reset_index(level=0, drop=True)
    )


def quality_roe(frame: pd.DataFrame) -> pd.Series:
    if "net_income" not in frame or "book_equity" not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return _group_shift(frame, frame["net_income"] / frame["book_equity"], 1)


def value_earnings_yield(frame: pd.DataFrame) -> pd.Series:
    if "net_income" not in frame or "market_cap" not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return _group_shift(frame, frame["net_income"] / frame["market_cap"], 1)


BUILTIN_FACTORS = {
    "momentum_12_1": momentum_12_1,
    "reversal_1": reversal_1,
    "volatility_63": volatility_63,
    "dollar_volume_21": dollar_volume_21,
    "quality_roe": quality_roe,
    "value_earnings_yield": value_earnings_yield,
}
