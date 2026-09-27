from __future__ import annotations

import argparse
import json
from pathlib import Path

from inhibit.config import load_config
from inhibit.data.loaders import DataLoader, load_yfinance
from inhibit.data.schema import validate_price_integrity
from inhibit.research import ResearchRunner
from inhibit.utils.verify import verify_run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inhibit", description="Leakage-safe adaptive factor research"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect = subparsers.add_parser("inspect", help="validate and summarize a local dataset")
    inspect.add_argument("--input", required=True)
    inspect.add_argument("--publication-lag", default="0D")
    validate = subparsers.add_parser(
        "validate-config", help="validate a YAML research configuration"
    )
    validate.add_argument("--config", required=True)
    fetch = subparsers.add_parser("fetch-yfinance", help="download public OHLCV data")
    fetch.add_argument("--symbols", nargs="+", required=True)
    fetch.add_argument("--start", required=True)
    fetch.add_argument("--end", required=True)
    fetch.add_argument("--output", required=True)
    run = subparsers.add_parser("run", help="run a configured research experiment")
    run.add_argument("--config", required=True)
    run.add_argument("--input", required=True)
    run.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify", help="verify a run manifest and its artifacts")
    verify.add_argument("--run", required=True)
    verify.add_argument("--input")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "inspect":
        frame = DataLoader().load(args.input, publication_lag=args.publication_lag)
        issues = validate_price_integrity(frame)
        summary = {
            "rows": len(frame),
            "symbols": int(frame["symbol"].nunique()),
            "start": str(frame["timestamp"].min()),
            "end": str(frame["timestamp"].max()),
            "issues": issues,
        }
        print(json.dumps(summary, indent=2))
        return 1 if issues else 0
    if args.command == "validate-config":
        config = load_config(args.config)
        print(json.dumps({"valid": True, "name": config.name, "seed": config.seed}, indent=2))
        return 0
    if args.command == "fetch-yfinance":
        frame = load_yfinance(args.symbols, args.start, args.end)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix.lower() in {".parquet", ".pq"}:
            frame.to_parquet(output, index=False)
        else:
            frame.to_csv(output, index=False)
        print(f"wrote {len(frame)} rows to {output}")
        return 0
    if args.command == "run":
        config = load_config(args.config)
        frame = DataLoader().load(args.input)
        manifest = ResearchRunner(config).run(frame, args.input, args.output)
        print(
            json.dumps(
                {
                    "output": args.output,
                    "metrics": manifest["metrics"],
                    "selected_factors": manifest["selected_factors"],
                },
                indent=2,
            )
        )
        return 0
    if args.command == "verify":
        result = verify_run(args.run, args.input)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
