from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

from inhibit.backtest.metrics import benjamini_hochberg, one_sided_normal_p_value
from inhibit.models.rules import MultiFactorCombinationRule
from inhibit.validation.splits import WalkForwardSplit


@dataclass(frozen=True)
class CandidateResult:
    name: str
    expression: str
    complexity: int
    mean_rank_ic: float
    median_rank_ic: float
    stability: float
    observations: int
    mean_test_rank_ic: float = 0.0
    median_test_rank_ic: float = 0.0
    test_stability: float = 0.0
    test_observations: int = 0
    p_value: float = 1.0
    q_value: float = 1.0
    multiple_testing_pass: bool = False
    selected: bool = False


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[CandidateResult, ...]
    selected_features: tuple[str, ...]
    search_count: int
    baseline_rank_ic: float


class AdaptiveFactorDiscovery:
    def __init__(
        self,
        max_candidates: int = 100,
        max_depth: int = 2,
        complexity_penalty: float = 0.002,
        seed: int = 42,
        custom_rules: list[MultiFactorCombinationRule] | None = None,
        fdr_q: float = 0.05,
    ) -> None:
        self.max_candidates = max_candidates
        self.max_depth = max_depth
        self.complexity_penalty = complexity_penalty
        self.rng = np.random.default_rng(seed)
        if not 0 < fdr_q <= 1:
            raise ValueError("fdr_q must be in (0, 1]")
        self.fdr_q = fdr_q
        self.custom_rules = custom_rules or []

    def discover(
        self,
        frame: pd.DataFrame,
        base_features: list[str],
        splits: list[WalkForwardSplit],
        label: str = "forward_return",
    ) -> DiscoveryResult:
        candidates = self._candidate_expressions(frame, base_features)
        candidates.extend(
            (rule.name, rule.expression, rule.complexity)
            for rule in self.custom_rules
            if set(rule.factors).issubset(frame.columns)
        )
        evaluated: list[CandidateResult] = []
        rule_map = {rule.name: rule for rule in self.custom_rules}
        for name, expression, complexity in candidates[: self.max_candidates]:
            values = (
                rule_map[name].evaluate(frame)
                if name in rule_map
                else self._evaluate_expression(frame, expression)
            )
            scores: list[float] = []
            test_scores: list[float] = []
            observations = 0
            test_observations = 0
            for split in splits:
                test = frame.iloc[split.validation].copy()
                test["candidate"] = values.iloc[split.validation].to_numpy()
                usable = test[["candidate", label]].dropna()
                if len(usable) < 5:
                    continue
                rank_ic = usable["candidate"].rank().corr(usable[label].rank())
                if pd.notna(rank_ic):
                    scores.append(float(rank_ic))
                    observations += len(usable)
                held_out = frame.iloc[split.test].copy()
                held_out["candidate"] = values.iloc[split.test].to_numpy()
                held_out_usable = held_out[["candidate", label]].dropna()
                if len(held_out_usable) >= 5:
                    test_rank_ic = (
                        held_out_usable["candidate"].rank().corr(held_out_usable[label].rank())
                    )
                    if pd.notna(test_rank_ic):
                        test_scores.append(float(test_rank_ic))
                        test_observations += len(held_out_usable)
            if not scores:
                continue
            positive = sum(score > 0 for score in scores)
            evaluated.append(
                CandidateResult(
                    name=name,
                    expression=expression,
                    complexity=complexity,
                    mean_rank_ic=float(np.mean(scores) - self.complexity_penalty * complexity),
                    median_rank_ic=float(np.median(scores)),
                    stability=float(positive / len(scores)),
                    observations=observations,
                    mean_test_rank_ic=(float(np.mean(test_scores)) if test_scores else 0.0),
                    median_test_rank_ic=(float(np.median(test_scores)) if test_scores else 0.0),
                    test_stability=(
                        float(sum(score > 0 for score in test_scores) / len(test_scores))
                        if test_scores
                        else 0.0
                    ),
                    test_observations=test_observations,
                    p_value=one_sided_normal_p_value(scores),
                )
            )
        q_values, testing_pass = benjamini_hochberg(
            [item.p_value for item in evaluated], self.fdr_q
        )
        evaluated = [
            CandidateResult(
                item.name,
                item.expression,
                item.complexity,
                item.mean_rank_ic,
                item.median_rank_ic,
                item.stability,
                item.observations,
                item.mean_test_rank_ic,
                item.median_test_rank_ic,
                item.test_stability,
                item.test_observations,
                item.p_value,
                q_value,
                testing,
                item.selected,
            )
            for item, q_value, testing in zip(evaluated, q_values, testing_pass, strict=True)
        ]
        evaluated.sort(
            key=lambda item: (item.mean_rank_ic, item.stability, item.median_rank_ic),
            reverse=True,
        )
        selected = evaluated[0] if evaluated else None
        baseline = self._baseline_rank_ic(frame, splits, label)
        selected_features = (
            (selected.name,)
            if selected
            and selected.mean_rank_ic > baseline
            and selected.stability >= 0.60
            and selected.multiple_testing_pass
            else ()
        )
        results = tuple(
            CandidateResult(
                item.name,
                item.expression,
                item.complexity,
                item.mean_rank_ic,
                item.median_rank_ic,
                item.stability,
                item.observations,
                item.mean_test_rank_ic,
                item.median_test_rank_ic,
                item.test_stability,
                item.test_observations,
                item.p_value,
                item.q_value,
                item.multiple_testing_pass,
                item.name in selected_features,
            )
            for item in evaluated
        )
        return DiscoveryResult(results, selected_features, len(candidates), baseline)

    def _candidate_expressions(
        self, frame: pd.DataFrame, base_features: list[str]
    ) -> list[tuple[str, str, int]]:
        numeric = [name for name in base_features if name in frame.columns]
        candidates: list[tuple[str, str, int]] = [(name, name, 1) for name in numeric]
        if self.max_depth >= 2:
            for left, right in combinations(numeric, 2):
                candidates.extend(
                    [
                        (f"{left}_plus_{right}", f"({left}) + ({right})", 2),
                        (f"{left}_minus_{right}", f"({left}) - ({right})", 2),
                        (f"{left}_times_{right}", f"({left}) * ({right})", 2),
                        (f"{left}_div_{right}", f"safe_div({left}, {right})", 2),
                    ]
                )
        if self.max_depth >= 3:
            for factor in numeric:
                candidates.extend(
                    [
                        (f"abs_{factor}", f"abs({factor})", 2),
                        (f"square_{factor}", f"square({factor})", 2),
                        (f"log1p_abs_{factor}", f"log1p_abs({factor})", 2),
                        (f"sign_{factor}", f"sign({factor})", 2),
                    ]
                )
            for left, middle, right in combinations(numeric, 3):
                candidates.extend(
                    [
                        (
                            f"{left}_plus_{middle}_minus_{right}",
                            f"({left}) + ({middle}) - ({right})",
                            3,
                        ),
                        (
                            f"{left}_times_{middle}_plus_{right}",
                            f"({left}) * ({middle}) + ({right})",
                            3,
                        ),
                    ]
                )
        return candidates

    @staticmethod
    def _evaluate_expression(frame: pd.DataFrame, expression: str) -> pd.Series:
        tree = ast.parse(expression, mode="eval").body
        values = {name: frame[name] for name in frame.columns if name.isidentifier()}
        result = AdaptiveFactorDiscovery._evaluate_node(tree, values)
        return pd.Series(result, index=frame.index).replace([np.inf, -np.inf], np.nan)

    @staticmethod
    def _evaluate_node(node: ast.AST, values: dict[str, pd.Series | float]) -> pd.Series | float:
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = AdaptiveFactorDiscovery._evaluate_node(node.operand, values)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Pow, ast.Div)
        ):
            left = AdaptiveFactorDiscovery._evaluate_node(node.left, values)
            right = AdaptiveFactorDiscovery._evaluate_node(node.right, values)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Pow):
                return left**right
            return AdaptiveFactorDiscovery._safe_div(left, right)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and len(node.args) in {1, 2}
        ):
            args = [AdaptiveFactorDiscovery._evaluate_node(arg, values) for arg in node.args]
            if node.func.id == "abs" and len(args) == 1:
                return np.abs(args[0])
            if node.func.id == "square" and len(args) == 1:
                return args[0] ** 2
            if node.func.id == "log1p_abs" and len(args) == 1:
                return np.log1p(np.abs(args[0]))
            if node.func.id == "sign" and len(args) == 1:
                return np.sign(args[0])
            if node.func.id == "safe_div" and len(args) == 2:
                return AdaptiveFactorDiscovery._safe_div(args[0], args[1])
        raise ValueError(f"unsupported symbolic expression: {ast.unparse(node)}")

    @staticmethod
    def _safe_div(left: pd.Series | float, right: pd.Series | float) -> pd.Series | float:
        if isinstance(right, pd.Series):
            return left / right.replace(0, np.nan)
        return left / right if right != 0 else np.nan

    @staticmethod
    def _baseline_rank_ic(frame: pd.DataFrame, splits: list[WalkForwardSplit], label: str) -> float:
        scores: list[float] = []
        candidate = frame.get("momentum_12_1")
        if candidate is None:
            return 0.0
        for split in splits:
            test = pd.DataFrame(
                {
                    "candidate": candidate.iloc[split.validation],
                    "label": frame[label].iloc[split.validation],
                }
            ).dropna()
            if len(test) >= 5:
                value = test["candidate"].rank().corr(test["label"].rank())
                if pd.notna(value):
                    scores.append(float(value))
        return float(np.mean(scores)) if scores else 0.0
