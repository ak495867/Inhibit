from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

CURRENT_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HISTORY_URL = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"


def read_table(url: str) -> pd.DataFrame:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 Inhibit research"}, timeout=30)
    response.raise_for_status()
    return pd.read_html(StringIO(response.text))[0]


def clean_ticker(value: object) -> str | None:
    if pd.isna(value):
        return None
    ticker = str(value).strip().replace(".", "-")
    return None if ticker.lower() in {"nan", "none", ""} else ticker


def build_intervals(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    current = read_table(CURRENT_URL)
    current_symbols = {clean_ticker(value) for value in current["Symbol"]}
    current_symbols.discard(None)
    history = read_table(HISTORY_URL)
    history.columns = [
        "effective_date",
        "added_ticker",
        "added_security",
        "removed_ticker",
        "removed_security",
        "reason",
        "refs",
    ]
    history["effective_date"] = pd.to_datetime(history["effective_date"], errors="coerce", utc=True)
    history = history.dropna(subset=["effective_date"])
    history["added"] = history["added_ticker"].map(clean_ticker)
    history["removed"] = history["removed_ticker"].map(clean_ticker)
    history = history[history["effective_date"] <= end]
    dates = sorted(history["effective_date"].dt.normalize().unique(), reverse=True)
    states: list[tuple[pd.Timestamp, set[str]]] = [(end.normalize(), set(current_symbols))]
    for date in dates:
        date_rows = history.loc[history["effective_date"].dt.normalize() == date]
        added = {value for value in date_rows["added"] if value}
        removed = {value for value in date_rows["removed"] if value}
        current_symbols = (current_symbols - added) | removed
        states.append((pd.Timestamp(date), set(current_symbols)))
    states.append((start.normalize(), set(current_symbols)))
    states = sorted(states, key=lambda item: item[0])
    records: list[dict[str, object]] = []
    for index, (effective_from, symbols) in enumerate(states[:-1]):
        effective_to = states[index + 1][0]
        if effective_to <= start or effective_from >= end:
            continue
        for symbol in sorted(symbol for symbol in symbols if isinstance(symbol, str)):
            records.append(
                {
                    "symbol": symbol,
                    "effective_from": max(effective_from, start),
                    "effective_to": min(effective_to, end),
                    "source": HISTORY_URL,
                }
            )
    return pd.DataFrame(records).drop_duplicates(["symbol", "effective_from", "effective_to"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2026-08-02")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    membership = build_intervals(start, end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    membership.to_csv(args.output, index=False)
    metadata = {
        "source_current": CURRENT_URL,
        "source_changes": HISTORY_URL,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "start": args.start,
        "end": args.end,
        "rows": len(membership),
        "symbols": int(membership["symbol"].nunique()),
        "warning": (
            "Free public change tables are a research approximation, not an official "
            "licensed point-in-time index feed."
        ),
    }
    print(json.dumps(metadata, indent=2))
