from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from inhibit.backtest.metrics import benjamini_hochberg, block_bootstrap_metric_interval
from inhibit.config import load_config
from inhibit.data.loaders import DataLoader
from inhibit.data.membership import apply_point_in_time_membership, load_membership
from inhibit.data.schema import validate_price_integrity
from inhibit.data.universe import apply_universe_filters
from inhibit.features.engine import FeatureEngine, add_forward_return_label
from inhibit.models.discovery import AdaptiveFactorDiscovery
from inhibit.validation.splits import walk_forward_splits


def bootstrap_distribution(
    returns: pd.Series, n_bootstrap: int, block_length: int, seed: int
) -> np.ndarray:
    values = returns.dropna().to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(values) / block_length))
    starts = rng.integers(0, len(values), size=(n_bootstrap, n_blocks))
    offsets = np.arange(block_length)
    indices = (starts[:, :, None] + offsets[None, None, :]) % len(values)
    sampled = values[indices].reshape(n_bootstrap, -1)[:, : len(values)]
    return (
        sampled.mean(axis=1)
        / np.maximum(sampled.std(axis=1, ddof=1), 1e-12)
        * np.sqrt(252)
    )


def rank_ic(candidate: pd.Series, label: pd.Series) -> float:
    usable = pd.DataFrame({"candidate": candidate, "label": label}).dropna()
    if len(usable) < 5:
        return float("nan")
    value = usable["candidate"].rank().corr(usable["label"].rank())
    return float(value) if pd.notna(value) else float("nan")


def prepare_frame(
    input_path: Path, config_path: Path
) -> tuple[pd.DataFrame, object, list[object]]:
    config = load_config(config_path)
    prices = DataLoader().load(input_path)
    issues = validate_price_integrity(prices)
    if issues:
        raise ValueError(f"price integrity checks failed: {issues}")
    if config.universe.membership_path:
        membership = load_membership(config.universe.membership_path)
        prices, _ = apply_point_in_time_membership(prices, membership)
    prices, _ = apply_universe_filters(prices, config.universe)
    features, _ = FeatureEngine().build(
        prices,
        config.features.include,
        config.schedule.information_buffer_bars,
        config.features.winsorize_quantiles,
        config.features.standardize_cross_section,
    )
    labeled = add_forward_return_label(features, config.schedule.label_horizon_bars)
    splits = walk_forward_splits(
        labeled["timestamp"],
        config.validation.train_bars,
        config.validation.validation_bars,
        config.validation.test_bars,
        config.validation.step_bars,
        config.validation.embargo_bars,
        config.schedule.label_horizon_bars,
    )
    return labeled, config, splits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--equity", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--current-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(args.manifest.read_text())
    current_manifest = json.loads(args.current_manifest.read_text())
    candidates = pd.read_csv(args.candidates)
    fdr_q = float(manifest["multiple_testing"]["fdr_q"])
    thresholds = sorted(candidates["complexity"].unique().tolist())
    fdr_rows: list[dict[str, object]] = []
    for threshold in thresholds:
        subset = candidates.loc[candidates["complexity"] <= threshold].copy()
        _, passed = benjamini_hochberg(subset["p_value"].tolist(), fdr_q)
        fdr_rows.append(
            {
                "complexity_threshold": int(threshold),
                "candidate_count": int(len(subset)),
                "rejections": int(sum(passed)),
                "rejection_rate": float(np.mean(passed)) if passed else 0.0,
                "fdr_q": fdr_q,
            }
        )
    fdr = pd.DataFrame(fdr_rows)
    fdr.to_csv(args.output_dir / "fdr_complexity_summary.csv", index=False)

    equity = pd.read_csv(args.equity)
    returns = equity["equity"].pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    bootstrap = bootstrap_distribution(returns, 2000, 21, int(manifest["seed"]))
    bootstrap_low, bootstrap_high = block_bootstrap_metric_interval(
        returns, "sharpe", 2000, 21, int(manifest["seed"])
    )
    plt.figure(figsize=(10, 6))
    plt.hist(bootstrap, bins=45, color="#245b8f", alpha=0.85, edgecolor="white")
    plt.axvline(
        manifest["metrics"]["sharpe"],
        color="#b11f2a",
        linewidth=2,
        label="Observed Sharpe",
    )
    plt.axvline(
        bootstrap_low, color="#222222", linestyle="--", label="2.5% block-bootstrap"
    )
    plt.axvline(
        bootstrap_high, color="#222222", linestyle="--", label="97.5% block-bootstrap"
    )
    plt.title("PIT S&P 500 Block-Bootstrap Sharpe Distribution")
    plt.xlabel("Annualized Sharpe")
    plt.ylabel("Bootstrap draw count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(args.output_dir / "pit_block_bootstrap_sharpe.png", dpi=160)
    plt.close()

    labeled, config, splits = prepare_frame(args.input, args.config)
    top = candidates.sort_values(["mean_rank_ic", "stability"], ascending=False).head(5)
    curve_rows: list[dict[str, object]] = []
    for _, candidate in top.iterrows():
        values = AdaptiveFactorDiscovery._evaluate_expression(
            labeled, candidate["expression"]
        )
        for split in splits:
            test_values = values.iloc[split.test]
            test_label = labeled.iloc[split.test]["forward_return"]
            curve_rows.append(
                {
                    "factor": candidate["name"],
                    "split_id": split.split_id,
                    "test_rank_ic": rank_ic(test_values, test_label),
                }
            )
    curves = pd.DataFrame(curve_rows)
    curves.to_csv(args.output_dir / "walk_forward_top5.csv", index=False)
    plt.figure(figsize=(11, 6))
    for factor, group in curves.groupby("factor", sort=False):
        plt.plot(
            group["split_id"],
            group["test_rank_ic"],
            marker="o",
            linewidth=2,
            label=factor,
        )
    plt.axhline(0, color="#222222", linewidth=1)
    plt.title("PIT S&P 500 Top-Factor Walk-Forward Test Rank IC")
    plt.xlabel("Walk-forward test window")
    plt.ylabel("Held-out rank IC")
    plt.xticks(sorted(curves["split_id"].unique()))
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(args.output_dir / "pit_walk_forward_stability.png", dpi=160)
    plt.close()

    comparison = pd.DataFrame(
        [
            {
                "universe": "current_constituent_snapshot",
                "sharpe": current_manifest["metrics"]["sharpe"],
                "annual_volatility": current_manifest["metrics"]["annual_volatility"],
                "max_drawdown": current_manifest["metrics"]["max_drawdown"],
                "fill_ratio": current_manifest["metrics"]["fill_ratio"],
                "artifact_flagged": current_manifest["artifact_flagged"],
            },
            {
                "universe": "point_in_time_membership_approximation",
                "sharpe": manifest["metrics"]["sharpe"],
                "annual_volatility": manifest["metrics"]["annual_volatility"],
                "max_drawdown": manifest["metrics"]["max_drawdown"],
                "fill_ratio": manifest["metrics"]["fill_ratio"],
                "artifact_flagged": manifest["artifact_flagged"],
            },
        ]
    )
    comparison.to_csv(args.output_dir / "pit_vs_current_comparison.csv", index=False)
    report = [
        "# Point-in-Time Universe and Statistical-Control Analysis",
        "",
        f"The current-constituent Sharpe was **{current_manifest['metrics']['sharpe']:.6f}**; "
        f"the point-in-time-membership approximation Sharpe was "
        f"**{manifest['metrics']['sharpe']:.6f}**. The change is "
        f"**{manifest['metrics']['sharpe'] - current_manifest['metrics']['sharpe']:.6f}**.",
        "",
        "## FDR by complexity threshold",
        "",
        fdr.to_markdown(index=False, floatfmt=".6f"),
        "",
        "## Bootstrap and walk-forward plots",
        "",
        f"The PIT run’s block-bootstrap Sharpe interval is **[{bootstrap_low:.6f}, "
        f"{bootstrap_high:.6f}]** using 2,000 21-bar circular block resamples. The plots "
        "are `pit_block_bootstrap_sharpe.png` and `pit_walk_forward_stability.png`; the "
        "underlying tables are `fdr_complexity_summary.csv` and `walk_forward_top5.csv`.",
        "",
        "The PIT membership file is reconstructed from a free public dated-change table and is "
        "therefore an approximation, not an official licensed index-vintage feed. The comparison "
        "reduces terminal-constituent survivorship bias but does not remove all data-quality, "
        "delisting, ticker-history, or membership-timing risks.",
    ]
    (args.output_dir / "pit_analysis.md").write_text("\n".join(report) + "\n")


if __name__ == "__main__":
    main()
