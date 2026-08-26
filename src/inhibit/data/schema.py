from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

PRICE_COLUMNS = ("symbol", "timestamp", "open", "high", "low", "close", "volume")
OPTIONAL_COLUMNS = ("adj_close", "currency", "available_at", "source", "data_quality")


class DataContractError(ValueError):
    """Raised when an input cannot be made point-in-time safe."""


@dataclass(frozen=True)
class DataFingerprint:
    path: str
    sha256: str
    rows: int
    columns: tuple[str, ...]


def _utc(values: pd.Series) -> pd.Series:
    result = pd.to_datetime(values, utc=True, errors="coerce")
    if result.isna().any():
        raise DataContractError("timestamps contain invalid values")
    return result


def normalize_prices(
    frame: pd.DataFrame, source: str = "unknown", publication_lag: str = "0D"
) -> pd.DataFrame:
    missing = [column for column in PRICE_COLUMNS if column not in frame.columns]
    if missing:
        raise DataContractError(f"missing required columns: {missing}")
    result = frame.copy()
    result["symbol"] = result["symbol"].astype(str).str.strip().str.upper()
    if (result["symbol"] == "").any():
        raise DataContractError("symbol cannot be empty")
    result["timestamp"] = _utc(result["timestamp"])
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[list(PRICE_COLUMNS)].isna().any().any():
        raise DataContractError("required price columns contain null or non-numeric values")
    if (result[["open", "high", "low", "close"]] <= 0).any().any():
        raise DataContractError("prices must be positive")
    if (result["volume"] < 0).any():
        raise DataContractError("volume cannot be negative")
    if "adj_close" in result:
        result["adj_close"] = pd.to_numeric(result["adj_close"], errors="coerce")
    if "available_at" in result:
        result["available_at"] = _utc(result["available_at"])
    else:
        result["available_at"] = result["timestamp"] + pd.Timedelta(publication_lag)
    if (result["available_at"] < result["timestamp"]).any():
        raise DataContractError("available_at cannot precede event timestamp")
    if "source" not in result:
        result["source"] = source
    result["source"] = result["source"].fillna(source).astype(str)
    if "data_quality" not in result:
        result["data_quality"] = "ok"
    result["data_quality"] = result["data_quality"].fillna("ok").astype(str)
    result = result.sort_values(["timestamp", "symbol"]).drop_duplicates(
        ["symbol", "timestamp"], keep="last"
    )
    result = result.reset_index(drop=True)
    return result


def validate_price_integrity(frame: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    if not frame["timestamp"].is_monotonic_increasing:
        issues.append("timestamps are not globally sorted")
    if (frame["high"] < frame[["open", "close"]].max(axis=1)).any():
        issues.append("high is below open or close")
    if (frame["low"] > frame[["open", "close"]].min(axis=1)).any():
        issues.append("low is above open or close")
    duplicate_count = int(frame.duplicated(["symbol", "timestamp"]).sum())
    if duplicate_count:
        issues.append(f"{duplicate_count} duplicate symbol/timestamp rows")
    availability_violations = int((frame["available_at"] < frame["timestamp"]).sum())
    if availability_violations:
        issues.append(f"{availability_violations} availability timestamps precede events")
    return issues


def fingerprint_file(path: str | Path, frame: pd.DataFrame) -> DataFingerprint:
    file_path = Path(path)
    digest = sha256(file_path.read_bytes()).hexdigest()
    return DataFingerprint(str(file_path), digest, len(frame), tuple(frame.columns))


def ensure_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise DataContractError(f"missing required columns: {missing}")
