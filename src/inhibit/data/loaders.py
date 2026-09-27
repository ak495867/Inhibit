from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from inhibit.data.schema import DataContractError, normalize_prices


class DataLoader:
    def load(self, path: str | Path, publication_lag: str = "0D") -> pd.DataFrame:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            frame = pd.read_csv(file_path)
        elif suffix in {".parquet", ".pq"}:
            frame = pd.read_parquet(file_path)
        elif suffix in {".json", ".jsonl", ".ndjson"}:
            frame = self._read_json(file_path)
        else:
            raise DataContractError(f"unsupported input format: {suffix}")
        return normalize_prices(
            frame, source=str(file_path), publication_lag=publication_lag
        )

    @staticmethod
    def _read_json(path: Path) -> pd.DataFrame:
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            return pd.read_json(path, lines=True)
        payload = json.loads(path.read_text())
        if isinstance(payload, dict) and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, list):
            raise DataContractError(
                "JSON input must be a list of records or an object with a data list"
            )
        return pd.DataFrame(payload)


def load_yfinance(
    symbols: Sequence[str], start: str, end: str, auto_adjust: bool = False
) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise DataContractError(
            "install inhibit[data] to use the yfinance adapter"
        ) from exc
    if not symbols:
        raise DataContractError("at least one symbol is required")
    raw = yf.download(
        tickers=list(symbols),
        start=start,
        end=end,
        auto_adjust=auto_adjust,
        progress=False,
        group_by="column",
        threads=False,
    )
    if raw.empty:
        raise DataContractError("yfinance returned no rows")
    if isinstance(raw.columns, pd.MultiIndex):
        rows: list[pd.DataFrame] = []
        for symbol in symbols:
            if symbol not in raw.columns.get_level_values(-1):
                continue
            part = raw.xs(symbol, axis=1, level=-1).reset_index()
            part["symbol"] = symbol
            rows.append(part)
        if not rows:
            raise DataContractError("none of the requested symbols were returned")
        frame = pd.concat(rows, ignore_index=True)
    else:
        frame = raw.reset_index()
        frame["symbol"] = symbols[0]
    frame = frame.rename(columns={"Date": "timestamp", "Datetime": "timestamp"})
    frame.columns = [str(column).lower().replace(" ", "_") for column in frame.columns]
    frame["source"] = "yfinance"
    return normalize_prices(frame, source="yfinance", publication_lag="0D")
