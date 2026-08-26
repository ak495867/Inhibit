from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    for column in ["timestamp", "open", "high", "low", "close", "volume"]:
        if column == "timestamp":
            frame[column] = pd.to_datetime(frame[column], utc=True)
        else:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    issue = (frame["low"] > frame[["open", "close"]].min(axis=1)) | (
        frame["high"] < frame[["open", "close"]].max(axis=1)
    )
    print(
        frame.loc[issue, ["symbol", "timestamp", "open", "high", "low", "close"]]
        .head(20)
        .to_string(index=False)
    )
    print(
        {
            "rows": len(frame),
            "invalid_rows": int(issue.sum()),
            "nan_rows": int(frame.isna().any(axis=1).sum()),
        }
    )
