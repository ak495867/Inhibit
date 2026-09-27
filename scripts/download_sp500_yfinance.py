from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

SOURCE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def load_symbols() -> pd.DataFrame:
    response = requests.get(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0 Inhibit research downloader"},
        timeout=30,
    )
    response.raise_for_status()
    table = pd.read_html(StringIO(response.text))[0]
    table["Symbol"] = table["Symbol"].astype(str).str.replace(".", "-", regex=False)
    return (
        table[["Symbol", "Security", "GICS Sector"]]
        .drop_duplicates("Symbol")
        .reset_index(drop=True)
    )


def normalize_download(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    records: list[pd.DataFrame] = []
    if isinstance(raw.columns, pd.MultiIndex):
        available = set(raw.columns.get_level_values(1))
        for symbol in symbols:
            if symbol not in available:
                continue
            one = raw.xs(symbol, axis=1, level=1).reset_index()
            one["symbol"] = symbol
            records.append(one)
    else:
        one = raw.reset_index()
        one["symbol"] = symbols[0]
        records.append(one)
    if not records:
        return pd.DataFrame()
    frame = pd.concat(records, ignore_index=True).rename(
        columns={
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
            "Adj Close": "adj_close",
        }
    )
    return frame


def download(
    symbols: list[str], start: str, end: str, batch_size: int
) -> tuple[pd.DataFrame, list[str]]:
    records: list[pd.DataFrame] = []
    failed: list[str] = []
    for offset in range(0, len(symbols), batch_size):
        batch = symbols[offset : offset + batch_size]
        try:
            raw = yf.download(
                batch,
                start=start,
                end=end,
                auto_adjust=False,
                actions=False,
                group_by="column",
                threads=False,
                progress=False,
                timeout=20,
            )
            normalized = normalize_download(raw, batch)
            if normalized.empty:
                failed.extend(batch)
            else:
                returned = set(normalized["symbol"].dropna().astype(str))
                failed.extend(sorted(set(batch) - returned))
                records.append(normalized)
        except Exception:
            failed.extend(batch)
        print(
            f"processed {min(offset + batch_size, len(symbols))}/{len(symbols)} symbols",
            flush=True,
        )
    if not records:
        raise RuntimeError("yfinance returned no usable batches")
    frame = pd.concat(records, ignore_index=True)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["available_at"] = frame["timestamp"]
    frame["currency"] = "USD"
    frame["source"] = "yfinance-current-sp500-snapshot"
    frame = frame.dropna(subset=["close", "volume"])
    return frame[
        [
            "symbol",
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adj_close",
            "currency",
            "available_at",
            "source",
        ]
    ], sorted(set(failed))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-08-01")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--universe-output", type=Path, required=True)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    universe = load_symbols()
    frame, failed = download(universe["Symbol"].tolist(), args.start, args.end, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.universe_output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    metadata = {
        "source_url": SOURCE_URL,
        "retrieved_at_utc": datetime.now(UTC).isoformat(),
        "snapshot_symbols": int(len(universe)),
        "returned_symbols": int(frame["symbol"].nunique()),
        "failed_symbols": failed,
        "start": args.start,
        "end": args.end,
        "survivorship_warning": (
            "This is a current-constituent snapshot, not historical point-in-time membership."
        ),
    }
    args.universe_output.write_text(
        json.dumps(
            {"metadata": metadata, "constituents": universe.to_dict("records")},
            indent=2,
        )
    )
    print(
        json.dumps(
            {
                "rows": len(frame),
                "symbols": int(frame["symbol"].nunique()),
                "failed": len(failed),
                "output": str(args.output),
                "universe": str(args.universe_output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
