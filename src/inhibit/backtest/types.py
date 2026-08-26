from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Fill:
    symbol: str
    timestamp: pd.Timestamp
    requested_shares: float
    filled_shares: float
    price: float
    notional: float
    commission: float
    spread_cost: float
    impact_cost: float
    total_cost: float
    reason: str
    volatility_level: float = 0.0
    stress_factor: float = 0.0
    effective_spread_bps: float = 0.0
    effective_impact_bps: float = 0.0
    effective_fill_probability: float = 0.0
    tail_risk_factor: float = 0.0
    liquidity_factor: float = 1.0
    effective_participation_rate: float = 0.0
