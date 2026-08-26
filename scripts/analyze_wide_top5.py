from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def analyze(candidates_path: Path, manifest_path: Path, output_path: Path) -> None:
    candidates = pd.read_csv(candidates_path)
    manifest = pd.read_json(manifest_path, typ="series")
    baseline = float(manifest["baseline_rank_ic"])
    top = (
        candidates.sort_values(["mean_rank_ic", "stability", "median_rank_ic"], ascending=False)
        .head(5)
        .copy()
    )
    top.insert(0, "validation_rank", range(1, len(top) + 1))
    top["validation_excess_vs_baseline"] = top["mean_rank_ic"] - baseline
    columns = [
        "validation_rank",
        "name",
        "complexity",
        "mean_rank_ic",
        "median_rank_ic",
        "stability",
        "mean_test_rank_ic",
        "median_test_rank_ic",
        "test_stability",
        "test_observations",
        "selected",
    ]
    table = top[columns].to_markdown(index=False, floatfmt=".6f")
    lines = [
        "# Wide-Search Top-Five Factor Analysis",
        "",
        "> Selection is based on validation metrics. Held-out test metrics are reported after the "
        "selection ranking and must not be used to choose a factor.",
        "",
        f"The manifest baseline rank IC is **{baseline:.6f}**. The wide search evaluated "
        f"**{int(manifest['search_count'])}** candidates across "
        f"**{int(manifest['split_count'])}** chronological windows. The table below contains "
        "the top five candidates ranked by validation mean rank IC after the configured "
        "complexity penalty.",
        "",
        table,
        "",
        "## Interpretation",
        "",
    ]
    for _, row in top.iterrows():
        direction = "positive" if row["mean_test_rank_ic"] > 0 else "negative"
        lines.append(
            f"**{row['name']}** has validation mean rank IC {row['mean_rank_ic']:.6f} "
            f"and validation stability {row['stability']:.2f}. On the held-out windows its "
            f"mean rank IC is {row['mean_test_rank_ic']:.6f}, median rank IC is "
            f"{row['median_test_rank_ic']:.6f}, and positive-window stability is "
            f"{row['test_stability']:.2f}; the held-out result is therefore {direction}."
        )
        lines.append("")
    lines.extend(
        [
            "## Limitations",
            "",
            "Rank IC is a cross-sectional association statistic, not a net portfolio return. "
            "It does not include trading costs, capacity, turnover, or fill behavior. "
            "The candidate "
            "ledger uses the validation set for ranking and the test set only for post-selection "
            "reporting in this analysis. The current verification dataset is deterministic and "
            "smooth, so its unusually strong IC and stability values are pipeline checks rather "
            "than evidence of a persistent market edge.",
            "",
            "The full run manifest, candidate ledger, execution fills, and verification command "
            "should be retained together for auditability.",
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.candidates, args.manifest, args.output)
