from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    numeric = ["open", "high", "low", "close", "volume"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid = (
        frame[numeric].isna().any(axis=1)
        | (frame["open"] <= 0)
        | (frame["high"] <= 0)
        | (frame["low"] <= 0)
        | (frame["close"] <= 0)
        | (frame["volume"] < 0)
        | (frame["low"] > frame[["open", "close"]].min(axis=1))
        | (frame["high"] < frame[["open", "close"]].max(axis=1))
        | (frame["high"] < frame["low"])
    )
    dropped = frame.loc[invalid].copy()
    clean = frame.loc[~invalid].copy()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(args.output, index=False)
    report = {
        "input": str(args.input),
        "output": str(args.output),
        "input_rows": int(len(frame)),
        "output_rows": int(len(clean)),
        "dropped_rows": int(len(dropped)),
        "dropped_records": dropped.to_dict("records"),
        "policy": "Drop invalid OHLCV rows only; no price interpolation or forward filling.",
    }
    args.report.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
