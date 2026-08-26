from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from inhibit.backtest.types import Fill
from inhibit.config import ExecutionConfig


@dataclass(frozen=True)
class HandlerContext:
    timestamp: pd.Timestamp
    symbol: str
    requested_shares: float
    bar: pd.Series
    rng: np.random.Generator


class ExecutionHandler:
    name = "base"

    def fill(self, context: HandlerContext, config: ExecutionConfig) -> Fill:
        raise NotImplementedError


class DefaultExecutionHandler(ExecutionHandler):
    name = "default"

    def fill(self, context: HandlerContext, config: ExecutionConfig) -> Fill:
        return _fill_with_parameters(
            context,
            config,
            spread_bps=config.spread_bps,
            impact_bps=config.impact_bps,
            participation_rate=config.participation_rate,
            fill_probability=config.fill_probability,
            volatility_level=0.0,
            stress_factor=0.0,
        )


class HighVolatilityExecutionHandler(ExecutionHandler):
    name = "high_volatility_stress"

    def __init__(
        self,
        threshold: float = 0.02,
        spread_multiplier: float = 2.0,
        impact_multiplier: float = 3.0,
        participation_multiplier: float = 0.50,
        fill_probability_floor: float = 0.25,
        fill_probability_sensitivity: float = 0.50,
        tail_threshold: float = 0.05,
        tail_spread_multiplier: float = 4.0,
        tail_impact_multiplier: float = 6.0,
        tail_liquidity_multiplier: float = 0.85,
        tail_fill_probability_floor: float = 0.05,
    ) -> None:
        if threshold <= 0:
            raise ValueError("volatility threshold must be positive")
        if not 0 < fill_probability_floor <= 1:
            raise ValueError("fill probability floor must be in (0, 1]")
        if spread_multiplier < 0 or impact_multiplier < 0 or not 0 < participation_multiplier <= 1:
            raise ValueError("stress multipliers have invalid values")
        if tail_threshold <= 0 or tail_spread_multiplier < 0 or tail_impact_multiplier < 0:
            raise ValueError("tail-risk parameters have invalid values")
        if not 0 < tail_liquidity_multiplier <= 1 or not 0 < tail_fill_probability_floor <= 1:
            raise ValueError("tail liquidity and fill floors have invalid values")
        self.threshold = threshold
        self.spread_multiplier = spread_multiplier
        self.impact_multiplier = impact_multiplier
        self.participation_multiplier = participation_multiplier
        self.fill_probability_floor = fill_probability_floor
        self.fill_probability_sensitivity = fill_probability_sensitivity
        self.tail_threshold = tail_threshold
        self.tail_spread_multiplier = tail_spread_multiplier
        self.tail_impact_multiplier = tail_impact_multiplier
        self.tail_liquidity_multiplier = tail_liquidity_multiplier
        self.tail_fill_probability_floor = tail_fill_probability_floor

    def fill(self, context: HandlerContext, config: ExecutionConfig) -> Fill:
        bar = context.bar
        realized_value = bar.get("realized_volatility", 0.0)
        realized = 0.0 if pd.isna(realized_value) else float(realized_value)
        range_vol = (
            max(float(bar["high"]) - float(bar["low"]), 0.0) / max(float(bar["close"]), 1e-12) / 2
        )
        volatility_level = max(realized, range_vol)
        stress_factor = max(volatility_level / self.threshold - 1.0, 0.0)
        stress_factor = min(stress_factor, 5.0)
        tail_risk_factor = max(volatility_level / self.tail_threshold - 1.0, 0.0)
        tail_risk_factor = min(tail_risk_factor, 10.0)
        spread_bps = config.spread_bps * (
            1.0
            + self.spread_multiplier * stress_factor
            + self.tail_spread_multiplier * tail_risk_factor**2
        )
        impact_bps = config.impact_bps * (
            1.0
            + self.impact_multiplier * stress_factor
            + self.tail_impact_multiplier * tail_risk_factor**2
        )
        liquidity_factor = max(
            0.01, 1.0 - self.tail_liquidity_multiplier * min(tail_risk_factor, 1.0)
        )
        participation_rate = config.participation_rate * max(
            0.01, 1.0 - self.participation_multiplier * min(stress_factor, 1.0)
        )
        fill_probability = max(
            self.fill_probability_floor,
            self.tail_fill_probability_floor if tail_risk_factor > 0 else 0.0,
            config.fill_probability
            * (1.0 - self.fill_probability_sensitivity * min(stress_factor, 1.0))
            * max(0.05, 1.0 - tail_risk_factor),
        )
        return _fill_with_parameters(
            context,
            config,
            spread_bps=spread_bps,
            impact_bps=impact_bps,
            participation_rate=participation_rate,
            fill_probability=fill_probability,
            volatility_level=volatility_level,
            stress_factor=stress_factor,
            tail_risk_factor=tail_risk_factor,
            liquidity_factor=liquidity_factor,
        )


def _fill_with_parameters(
    context: HandlerContext,
    config: ExecutionConfig,
    spread_bps: float,
    impact_bps: float,
    participation_rate: float,
    fill_probability: float,
    volatility_level: float,
    stress_factor: float,
    tail_risk_factor: float = 0.0,
    liquidity_factor: float = 1.0,
) -> Fill:
    timestamp = context.timestamp
    symbol = context.symbol
    requested = context.requested_shares
    bar = context.bar
    volume = max(float(bar["volume"]), 0.0)
    effective_participation_rate = participation_rate * liquidity_factor
    max_shares = volume * effective_participation_rate
    if not config.allow_partial_fills:
        filled = requested if abs(requested) <= max_shares else 0.0
    else:
        filled = np.sign(requested) * min(abs(requested), max_shares)
    if config.lot_size > 1:
        filled = np.sign(filled) * np.floor(abs(filled) / config.lot_size) * config.lot_size
    if filled == 0:
        return Fill(
            symbol,
            timestamp,
            requested,
            0.0,
            float(bar["close"]),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            "unfilled_volume_or_lot",
            volatility_level,
            stress_factor,
            spread_bps,
            impact_bps,
            fill_probability,
            tail_risk_factor,
            liquidity_factor,
            effective_participation_rate,
        )
    if context.rng.random() > fill_probability:
        return Fill(
            symbol,
            timestamp,
            requested,
            0.0,
            float(bar["close"]),
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            "probabilistic_rejection",
            volatility_level,
            stress_factor,
            spread_bps,
            impact_bps,
            fill_probability,
            tail_risk_factor,
            liquidity_factor,
            effective_participation_rate,
        )
    base_price = float(bar[config.price_field])
    notional = abs(filled * base_price)
    commission = notional * config.commission_bps / 10_000
    spread_cost = notional * spread_bps / 10_000
    participation = min(abs(filled) / volume, 1.0) if volume else 1.0
    impact_rate = impact_bps / 10_000 * participation**config.impact_exponent
    impact_cost = notional * impact_rate
    signed_price = base_price + np.sign(filled) * (spread_cost + impact_cost) / max(
        abs(filled), 1e-12
    )
    total_cost = commission + spread_cost + impact_cost
    return Fill(
        symbol,
        timestamp,
        requested,
        float(filled),
        signed_price,
        abs(filled * signed_price),
        commission,
        spread_cost,
        impact_cost,
        total_cost,
        "filled",
        volatility_level,
        stress_factor,
        spread_bps,
        impact_bps,
        fill_probability,
        tail_risk_factor,
        liquidity_factor,
        effective_participation_rate,
    )
