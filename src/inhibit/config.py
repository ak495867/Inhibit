from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class UniverseConfig:
    membership_path: str | None = None
    min_history_bars: int = 252
    max_positions: int = 20
    long_only: bool = True
    min_price: float = 5.0
    min_dollar_volume: float = 1_000_000.0


@dataclass(frozen=True)
class ScheduleConfig:
    frequency: str = "monthly"
    rebalance_weekday: int = 0
    execution_delay_bars: int = 1
    information_buffer_bars: int = 1
    label_horizon_bars: int = 21


@dataclass(frozen=True)
class FeatureConfig:
    winsorize_quantiles: tuple[float, float] = (0.01, 0.99)
    standardize_cross_section: bool = True
    neutralize: tuple[str, ...] = ()
    include: tuple[str, ...] = ()
    discovery: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationConfig:
    train_bars: int = 756
    validation_bars: int = 126
    test_bars: int = 126
    step_bars: int = 126
    embargo_bars: int = 21
    n_bootstrap: int = 1000
    bootstrap_block_length: int = 21
    min_test_periods: int = 3
    holdout_fraction: float = 0.15


@dataclass(frozen=True)
class PortfolioConfig:
    gross_leverage: float = 1.0
    max_position_weight: float = 0.10
    max_turnover: float = 0.50
    cash_rate_annualized: float = 0.0
    rebalance_tolerance: float = 0.002


@dataclass(frozen=True)
class ExecutionConfig:
    commission_bps: float = 1.0
    spread_bps: float = 5.0
    impact_bps: float = 10.0
    impact_exponent: float = 0.60
    handler: str = "default"
    stress_volatility_threshold: float = 0.02
    stress_spread_multiplier: float = 2.0
    stress_impact_multiplier: float = 3.0
    stress_participation_multiplier: float = 0.50
    stress_fill_probability_floor: float = 0.25
    stress_fill_probability_sensitivity: float = 0.50
    tail_risk_threshold: float = 0.05
    tail_spread_multiplier: float = 4.0
    tail_impact_multiplier: float = 6.0
    tail_liquidity_multiplier: float = 0.85
    tail_fill_probability_floor: float = 0.05
    borrow_bps_annualized: float = 300.0
    participation_rate: float = 0.10
    fill_probability: float = 0.85
    max_fill_bars: int = 3
    lot_size: int = 1
    allow_partial_fills: bool = True
    price_field: str = "close"


@dataclass(frozen=True)
class ResearchConfig:
    allow_zero_cost_diagnostic: bool = False
    output_metrics: tuple[str, ...] = ()


@dataclass(frozen=True)
class InhibitConfig:
    name: str = "inhibit_run"
    seed: int = 42
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)

    def validate(self) -> None:
        numeric_values = {
            "universe.min_price": self.universe.min_price,
            "universe.min_dollar_volume": self.universe.min_dollar_volume,
            "portfolio.gross_leverage": self.portfolio.gross_leverage,
            "portfolio.max_position_weight": self.portfolio.max_position_weight,
            "portfolio.max_turnover": self.portfolio.max_turnover,
            "portfolio.rebalance_tolerance": self.portfolio.rebalance_tolerance,
            "execution.commission_bps": self.execution.commission_bps,
            "execution.spread_bps": self.execution.spread_bps,
            "execution.impact_bps": self.execution.impact_bps,
            "execution.impact_exponent": self.execution.impact_exponent,
            "execution.stress_volatility_threshold": self.execution.stress_volatility_threshold,
            "execution.stress_spread_multiplier": self.execution.stress_spread_multiplier,
            "execution.stress_impact_multiplier": self.execution.stress_impact_multiplier,
            "execution.stress_participation_multiplier": (
                self.execution.stress_participation_multiplier
            ),
            "execution.stress_fill_probability_floor": self.execution.stress_fill_probability_floor,
            "execution.stress_fill_probability_sensitivity": (
                self.execution.stress_fill_probability_sensitivity
            ),
            "execution.tail_risk_threshold": self.execution.tail_risk_threshold,
            "execution.tail_spread_multiplier": self.execution.tail_spread_multiplier,
            "execution.tail_impact_multiplier": self.execution.tail_impact_multiplier,
            "execution.tail_liquidity_multiplier": self.execution.tail_liquidity_multiplier,
            "execution.tail_fill_probability_floor": self.execution.tail_fill_probability_floor,
            "execution.borrow_bps_annualized": self.execution.borrow_bps_annualized,
            "execution.participation_rate": self.execution.participation_rate,
            "execution.fill_probability": self.execution.fill_probability,
            "validation.holdout_fraction": self.validation.holdout_fraction,
            "portfolio.cash_rate_annualized": self.portfolio.cash_rate_annualized,
        }
        for field_name, value in numeric_values.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{field_name} must be a finite number")
        if self.schedule.execution_delay_bars < 1:
            raise ValueError("execution_delay_bars must be at least 1")
        if self.schedule.information_buffer_bars < 0:
            raise ValueError("information_buffer_bars cannot be negative")
        if self.schedule.label_horizon_bars < 1:
            raise ValueError("label_horizon_bars must be positive")
        if not 0 <= self.schedule.rebalance_weekday <= 6:
            raise ValueError("rebalance_weekday must be between 0 and 6")
        if self.universe.min_history_bars < 1:
            raise ValueError("min_history_bars must be positive")
        if self.universe.min_price < 0 or self.universe.min_dollar_volume < 0:
            raise ValueError("universe minimums cannot be negative")
        if not self.features.include or any(not name for name in self.features.include):
            raise ValueError("features.include must contain at least one feature name")
        if len(set(self.features.include)) != len(self.features.include):
            raise ValueError("features.include cannot contain duplicate names")
        low_quantile, high_quantile = self.features.winsorize_quantiles
        if not 0 <= low_quantile < high_quantile <= 1:
            raise ValueError("winsorize_quantiles must satisfy 0 <= low < high <= 1")
        if (
            min(
                self.validation.train_bars,
                self.validation.validation_bars,
                self.validation.test_bars,
                self.validation.step_bars,
                self.validation.min_test_periods,
            )
            < 1
        ):
            raise ValueError(
                "validation window sizes and min_test_periods must be positive"
            )
        if self.validation.embargo_bars < 0:
            raise ValueError("embargo_bars cannot be negative")
        if not 0 < self.validation.holdout_fraction < 1:
            raise ValueError("holdout_fraction must be in (0, 1)")
        if not 0 < self.execution.participation_rate <= 1:
            raise ValueError("participation_rate must be in (0, 1]")
        if not 0 <= self.execution.fill_probability <= 1:
            raise ValueError("fill_probability must be in [0, 1]")
        if (
            min(
                self.execution.commission_bps,
                self.execution.spread_bps,
                self.execution.impact_bps,
            )
            < 0
        ):
            raise ValueError("execution costs cannot be negative")
        if self.execution.impact_exponent <= 0:
            raise ValueError("impact_exponent must be positive")
        if self.execution.handler not in {"default", "high_volatility_stress"}:
            raise ValueError("handler must be default or high_volatility_stress")
        if self.execution.stress_volatility_threshold <= 0:
            raise ValueError("stress_volatility_threshold must be positive")
        if (
            min(
                self.execution.stress_spread_multiplier,
                self.execution.stress_impact_multiplier,
                self.execution.stress_participation_multiplier,
                self.execution.stress_fill_probability_sensitivity,
            )
            < 0
        ):
            raise ValueError("stress multipliers and sensitivity cannot be negative")
        if not 0 < self.execution.stress_fill_probability_floor <= 1:
            raise ValueError("stress_fill_probability_floor must be in (0, 1]")
        if self.execution.tail_risk_threshold <= 0:
            raise ValueError("tail_risk_threshold must be positive")
        if (
            self.execution.tail_spread_multiplier < 0
            or self.execution.tail_impact_multiplier < 0
        ):
            raise ValueError("tail cost multipliers cannot be negative")
        if not 0 < self.execution.tail_liquidity_multiplier <= 1:
            raise ValueError("tail_liquidity_multiplier must be in (0, 1]")
        if not 0 < self.execution.tail_fill_probability_floor <= 1:
            raise ValueError("tail_fill_probability_floor must be in (0, 1]")
        if self.universe.max_positions < 1:
            raise ValueError("max_positions must be positive")
        if self.execution.max_fill_bars < 1 or self.execution.lot_size < 1:
            raise ValueError("max_fill_bars and lot_size must be positive")
        if self.validation.n_bootstrap < 100:
            raise ValueError("n_bootstrap must be at least 100")
        if self.validation.bootstrap_block_length < 1:
            raise ValueError("bootstrap_block_length must be positive")
        if self.portfolio.gross_leverage <= 0:
            raise ValueError("gross_leverage must be positive")
        if self.portfolio.max_position_weight <= 0:
            raise ValueError("max_position_weight must be positive")
        if self.portfolio.max_turnover < 0 or self.portfolio.rebalance_tolerance < 0:
            raise ValueError("portfolio turnover and tolerance cannot be negative")
        if not self.research.allow_zero_cost_diagnostic and all(
            value == 0
            for value in (
                self.execution.commission_bps,
                self.execution.spread_bps,
                self.execution.impact_bps,
            )
        ):
            raise ValueError(
                "zero-friction runs require allow_zero_cost_diagnostic=true"
            )


def _construct(cls: type[Any], payload: dict[str, Any] | None) -> Any:
    payload = payload or {}
    return cls(**payload)


def load_config(path: str | Path) -> InhibitConfig:
    payload = yaml.safe_load(Path(path).read_text()) or {}
    config = InhibitConfig(
        name=payload.get("name", "inhibit_run"),
        seed=int(payload.get("seed", 42)),
        universe=_construct(UniverseConfig, payload.get("universe")),
        schedule=_construct(ScheduleConfig, payload.get("schedule")),
        features=_construct(FeatureConfig, payload.get("features")),
        validation=_construct(ValidationConfig, payload.get("validation")),
        portfolio=_construct(PortfolioConfig, payload.get("portfolio")),
        execution=_construct(ExecutionConfig, payload.get("execution")),
        research=_construct(ResearchConfig, payload.get("research")),
    )
    config.validate()
    return config
