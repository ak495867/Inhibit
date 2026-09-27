from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from time import time

import numpy as np
import pandas as pd

from inhibit.backtest.execution import ExecutionSimulator
from inhibit.backtest.metrics import (
    artifact_flags,
    block_bootstrap_metric_interval,
    performance_metrics,
)
from inhibit.config import InhibitConfig
from inhibit.data.membership import apply_point_in_time_membership, load_membership
from inhibit.data.schema import fingerprint_file, validate_price_integrity
from inhibit.data.universe import apply_universe_filters
from inhibit.features.engine import FeatureEngine, add_forward_return_label
from inhibit.models.discovery import AdaptiveFactorDiscovery
from inhibit.models.linear import CrossSectionalRidge
from inhibit.models.rules import MultiFactorCombinationRule
from inhibit.utils.artifacts import artifact_manifest, runtime_manifest
from inhibit.validation.diagnostics import regime_performance
from inhibit.validation.splits import assert_no_overlap, walk_forward_splits


class ResearchRunner:
    def __init__(self, config: InhibitConfig) -> None:
        config.validate()
        self.config = config

    def run(
        self, prices: pd.DataFrame, input_path: str | Path, output_dir: str | Path
    ) -> dict[str, object]:
        started_at = time()
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        prices = prices.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
        integrity_issues = validate_price_integrity(prices)
        if integrity_issues:
            raise ValueError(f"price integrity checks failed: {integrity_issues}")
        membership_audit: dict[str, int] = {}
        if self.config.universe.membership_path:
            membership = load_membership(self.config.universe.membership_path)
            prices, membership_audit = apply_point_in_time_membership(
                prices, membership
            )
        prices, universe_audit = apply_universe_filters(prices, self.config.universe)
        if prices.empty:
            raise ValueError("universe filters removed every symbol")
        features, audit = FeatureEngine().build(
            prices,
            self.config.features.include,
            information_buffer_bars=self.config.schedule.information_buffer_bars,
            winsorize_quantiles=self.config.features.winsorize_quantiles,
            standardize_cross_section=self.config.features.standardize_cross_section,
        )
        labeled = add_forward_return_label(
            features, self.config.schedule.label_horizon_bars
        )
        splits = walk_forward_splits(
            labeled["timestamp"],
            self.config.validation.train_bars,
            self.config.validation.validation_bars,
            self.config.validation.test_bars,
            self.config.validation.step_bars,
            self.config.validation.embargo_bars,
            self.config.schedule.label_horizon_bars,
        )
        if len(splits) < self.config.validation.min_test_periods:
            raise ValueError(
                f"only {len(splits)} test windows available; "
                f"need at least {self.config.validation.min_test_periods}"
            )
        for split in splits:
            assert_no_overlap(split)
        custom_rules = self._custom_rules()
        discovery_engine = AdaptiveFactorDiscovery(
            max_candidates=int(
                self.config.features.discovery.get("max_candidates", 100)
            ),
            max_depth=int(self.config.features.discovery.get("max_depth", 2)),
            complexity_penalty=float(
                self.config.features.discovery.get("complexity_penalty", 0.002)
            ),
            seed=self.config.seed,
            custom_rules=custom_rules,
            fdr_q=float(self.config.features.discovery.get("fdr_q", 0.05)),
        )
        discovery = discovery_engine.discover(
            labeled, list(self.config.features.include), splits
        )
        selected = list(discovery.selected_features)
        if selected:
            rule_map = {rule.name: rule for rule in custom_rules}
            for name in selected:
                if name in rule_map:
                    labeled[name] = rule_map[name].evaluate(labeled)
                else:
                    labeled[name] = AdaptiveFactorDiscovery._evaluate_expression(
                        labeled,
                        next(
                            item.expression
                            for item in discovery.candidates
                            if item.name == name
                        ),
                    )
        factor_set = selected or list(self.config.features.include)
        targets: list[pd.DataFrame] = []
        split_results: list[dict[str, object]] = []
        for split in splits:
            fit_indices = np.concatenate([split.train, split.validation])
            model = CrossSectionalRidge(alpha=10.0)
            fit = model.fit(labeled.iloc[fit_indices], factor_set)
            test_frame = labeled.iloc[split.test].copy()
            predictions = model.predict(test_frame)
            split_targets = model.score_to_weights(
                test_frame,
                predictions,
                self.config.universe.max_positions,
                self.config.portfolio.max_position_weight,
            )
            if not split_targets.empty:
                targets.append(split_targets)
            split_results.append(
                {
                    "split_id": split.split_id,
                    "train_rows": len(split.train),
                    "validation_rows": len(split.validation),
                    "test_rows": len(split.test),
                    "factor_set": factor_set,
                    "fit": asdict(fit),
                }
            )
        target_weights = (
            pd.concat(targets, ignore_index=True)
            if targets
            else pd.DataFrame(columns=["timestamp", "symbol", "weight"])
        )
        test_times = pd.Index(
            pd.concat(
                [labeled.iloc[split.test]["timestamp"] for split in splits]
            ).unique()
        )
        test_bars = prices[prices["timestamp"].isin(test_times)].copy()
        execution = ExecutionSimulator(
            self.config.execution,
            self.config.portfolio,
            self.config.seed,
            self.config.schedule.execution_delay_bars,
        ).run(test_bars, target_weights)
        metrics = performance_metrics(execution.equity, execution.fills)
        returns = (
            execution.equity["equity"].pct_change().dropna()
            if not execution.equity.empty
            else pd.Series(dtype=float)
        )
        sharpe_ci = block_bootstrap_metric_interval(
            returns,
            "sharpe",
            self.config.validation.n_bootstrap,
            self.config.validation.bootstrap_block_length,
            self.config.seed,
        )
        metrics["sharpe_ci_low"] = sharpe_ci[0]
        metrics["sharpe_ci_high"] = sharpe_ci[1]
        flags = artifact_flags(metrics)
        regime_metrics = regime_performance(
            execution.equity,
            self.config.validation.n_bootstrap,
            self.config.seed,
            self.config.validation.bootstrap_block_length,
        )
        equity = execution.equity.copy()
        if not equity.empty:
            equity.to_csv(output / "equity.csv", index=False)
        execution.fills.to_csv(output / "fills.csv", index=False)
        target_weights.to_csv(output / "target_weights.csv", index=False)
        pd.DataFrame([asdict(item) for item in discovery.candidates]).to_csv(
            output / "candidates.csv", index=False
        )
        manifest = self._manifest(
            input_path,
            prices,
            audit,
            discovery,
            splits,
            factor_set,
            split_results,
            metrics,
        )
        manifest["universe_audit"] = universe_audit
        manifest["membership_audit"] = membership_audit
        manifest["integrity_issues"] = integrity_issues
        manifest["regime_metrics"] = regime_metrics
        manifest["artifact_flags"] = flags
        manifest["artifact_flagged"] = bool(flags)
        manifest["runtime"] = runtime_manifest()
        manifest["duration_seconds"] = time() - started_at
        manifest["artifacts"] = artifact_manifest(output)
        (output / "manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str)
        )
        return manifest

    def _manifest(
        self,
        input_path: str | Path,
        prices: pd.DataFrame,
        audit: object,
        discovery: object,
        splits: list[object],
        factor_set: list[str],
        split_results: list[dict[str, object]],
        metrics: dict[str, float],
    ) -> dict[str, object]:
        fingerprint = fingerprint_file(input_path, prices)
        config_json = json.dumps(asdict(self.config), sort_keys=True, default=str)
        return {
            "project": "Inhibit",
            "config_name": self.config.name,
            "config_sha256": sha256(config_json.encode()).hexdigest(),
            "input": asdict(fingerprint),
            "git_commit": self._git_commit(),
            "seed": self.config.seed,
            "feature_audit": asdict(audit),
            "split_count": len(splits),
            "search_count": discovery.search_count,
            "selected_factors": factor_set,
            "discovery_selected_factors": list(discovery.selected_features),
            "selection_status": (
                "discovery_selected"
                if discovery.selected_features
                else "baseline_fallback_no_fdr_pass"
            ),
            "custom_rules": [
                {
                    "name": rule.name,
                    "factors": rule.factors,
                    "weights": rule.weights,
                    "normalize": rule.normalize,
                }
                for rule in self._custom_rules()
            ],
            "baseline_rank_ic": discovery.baseline_rank_ic,
            "multiple_testing": {
                "method": "benjamini_hochberg",
                "fdr_q": float(self.config.features.discovery.get("fdr_q", 0.05)),
                "candidates_passing": int(
                    sum(item.multiple_testing_pass for item in discovery.candidates)
                ),
            },
            "split_results": split_results,
            "metrics": metrics,
            "assumptions": asdict(self.config.execution),
            "research_warning": "Historical simulation is not a guarantee of future performance.",
        }

    def _custom_rules(self) -> list[MultiFactorCombinationRule]:
        rules = self.config.features.discovery.get("custom_rules", [])
        if not isinstance(rules, list):
            raise ValueError("features.discovery.custom_rules must be a list")
        return [
            MultiFactorCombinationRule(
                name=str(rule["name"]),
                factors=tuple(str(factor) for factor in rule["factors"]),
                weights=tuple(float(weight) for weight in rule["weights"]),
                normalize=bool(rule.get("normalize", True)),
            )
            for rule in rules
        ]

    @staticmethod
    def _git_commit() -> str:
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "uncommitted"
