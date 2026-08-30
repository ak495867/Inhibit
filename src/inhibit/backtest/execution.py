from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from inhibit.backtest.handlers import (
    DefaultExecutionHandler,
    ExecutionHandler,
    HandlerContext,
    HighVolatilityExecutionHandler,
)
from inhibit.backtest.types import Fill
from inhibit.config import ExecutionConfig, PortfolioConfig


@dataclass(frozen=True)
class ExecutionResult:
    fills: pd.DataFrame
    equity: pd.DataFrame
    final_positions: pd.DataFrame


class ExecutionSimulator:
    def __init__(
        self,
        execution: ExecutionConfig,
        portfolio: PortfolioConfig,
        seed: int = 42,
        execution_delay_bars: int = 1,
        handler: ExecutionHandler | None = None,
    ) -> None:
        self.execution = execution
        self.portfolio = portfolio
        self.execution_delay_bars = execution_delay_bars
        self.rng = np.random.default_rng(seed)
        self.handler = handler or self._build_handler()

    def run(
        self,
        bars: pd.DataFrame,
        target_weights: pd.DataFrame,
        initial_cash: float = 1_000_000.0,
    ) -> ExecutionResult:
        required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(bars.columns)
        if missing:
            raise ValueError(f"execution bars missing columns: {sorted(missing)}")
        price_data = bars.sort_values(["timestamp", "symbol"]).copy()
        price_data["timestamp"] = pd.to_datetime(price_data["timestamp"], utc=True)
        price_data["bar_return"] = price_data.groupby("symbol", sort=False)[
            "close"
        ].pct_change()
        price_data["realized_volatility"] = price_data.groupby("symbol", sort=False)[
            "bar_return"
        ].transform(lambda values: values.rolling(21, min_periods=5).std())
        times = list(pd.Index(price_data["timestamp"].drop_duplicates()).sort_values())
        weights = self._delay_targets(target_weights, times)
        positions: dict[str, float] = {}
        cash = float(initial_cash)
        fill_records: list[dict[str, object]] = []
        equity_records: list[dict[str, float | pd.Timestamp]] = []
        order_ages: dict[str, int] = {}
        previous_equity = initial_cash
        for timestamp, day in price_data.groupby("timestamp", sort=True):
            marks = day.set_index("symbol")
            desired = self._desired_positions(
                timestamp, marks, weights, positions, cash
            )
            for symbol, requested in desired.items():
                if symbol not in marks.index:
                    continue
                age = order_ages.get(symbol, 0)
                if age >= self.execution.max_fill_bars:
                    fill = Fill(
                        symbol,
                        timestamp,
                        requested,
                        0.0,
                        float(marks.loc[symbol, "close"]),
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        "expired_max_fill_bars",
                    )
                    order_ages.pop(symbol, None)
                else:
                    fill = self._fill_order(
                        timestamp, symbol, requested, marks.loc[symbol]
                    )
                    if (
                        abs(fill.filled_shares) >= abs(requested)
                        or fill.reason == "probabilistic_rejection"
                    ):
                        order_ages.pop(symbol, None)
                    else:
                        order_ages[symbol] = age + 1
                positions[symbol] = positions.get(symbol, 0.0) + fill.filled_shares
                cash -= fill.filled_shares * fill.price + fill.total_cost
                fill_records.append(fill.__dict__)
            marked = sum(
                shares * float(marks.loc[symbol, "close"])
                for symbol, shares in positions.items()
                if symbol in marks.index
            )
            equity = cash + marked
            borrow_fee = self._borrow_fee(positions, marks, previous_equity)
            cash -= borrow_fee
            equity -= borrow_fee
            gross = sum(
                abs(shares * float(marks.loc[symbol, "close"]))
                for symbol, shares in positions.items()
                if symbol in marks.index
            )
            equity_records.append(
                {
                    "timestamp": timestamp,
                    "cash": cash,
                    "marked_positions": marked,
                    "equity": equity,
                    "gross_exposure": gross,
                    "borrow_fee": borrow_fee,
                }
            )
            previous_equity = equity
        fills = pd.DataFrame(fill_records)
        equity_frame = pd.DataFrame(equity_records)
        final_positions = pd.DataFrame(
            [
                {"symbol": symbol, "shares": shares}
                for symbol, shares in positions.items()
            ]
        )
        return ExecutionResult(fills, equity_frame, final_positions)

    def _delay_targets(
        self, target_weights: pd.DataFrame, times: list[pd.Timestamp]
    ) -> pd.Series:
        if target_weights.empty:
            return pd.Series(dtype=float)
        target = target_weights.copy()
        target["timestamp"] = pd.to_datetime(target["timestamp"], utc=True)
        delay = max(self._delay_bars(), 0)
        mapping = {
            time: times[min(index + delay, len(times) - 1)]
            for index, time in enumerate(times)
        }
        target["timestamp"] = (
            target["timestamp"].map(mapping).fillna(target["timestamp"])
        )
        return (
            target.set_index(["timestamp", "symbol"])["weight"]
            .groupby(level=[0, 1])
            .last()
        )

    def _delay_bars(self) -> int:
        return int(self.execution_delay_bars)

    def _desired_positions(
        self,
        timestamp: pd.Timestamp,
        marks: pd.DataFrame,
        weights: pd.Series,
        positions: dict[str, float],
        cash: float,
    ) -> dict[str, float]:
        current_equity = cash + sum(
            shares * float(marks.loc[symbol, "close"])
            for symbol, shares in positions.items()
            if symbol in marks.index
        )
        if current_equity <= 0:
            return {}
        deltas: dict[str, float] = {}
        for symbol in marks.index:
            target_weight = float(weights.get((timestamp, symbol), 0.0))
            target_weight = float(
                np.clip(
                    target_weight,
                    -self.portfolio.max_position_weight,
                    self.portfolio.max_position_weight,
                )
            )
            target_shares = (
                target_weight * current_equity / float(marks.loc[symbol, "close"])
            )
            delta = target_shares - positions.get(symbol, 0.0)
            if (
                abs(delta * float(marks.loc[symbol, "close"]) / current_equity)
                >= self.portfolio.rebalance_tolerance
            ):
                deltas[symbol] = delta
        gross_notional = sum(
            abs(delta * float(marks.loc[symbol, "close"]))
            for symbol, delta in deltas.items()
        )
        cap = self.portfolio.max_turnover * current_equity
        if gross_notional > cap > 0:
            scale = cap / gross_notional
            deltas = {symbol: delta * scale for symbol, delta in deltas.items()}
        return deltas

    def _borrow_fee(
        self, positions: dict[str, float], marks: pd.DataFrame, equity: float
    ) -> float:
        short_notional = sum(
            abs(shares * float(marks.loc[symbol, "close"]))
            for symbol, shares in positions.items()
            if shares < 0 and symbol in marks.index
        )
        return (
            short_notional * self.execution.borrow_bps_annualized / 10_000 / 252
            if equity > 0
            else 0.0
        )

    def _build_handler(self) -> ExecutionHandler:
        if self.execution.handler == "high_volatility_stress":
            return HighVolatilityExecutionHandler(
                threshold=self.execution.stress_volatility_threshold,
                spread_multiplier=self.execution.stress_spread_multiplier,
                impact_multiplier=self.execution.stress_impact_multiplier,
                participation_multiplier=self.execution.stress_participation_multiplier,
                fill_probability_floor=self.execution.stress_fill_probability_floor,
                fill_probability_sensitivity=self.execution.stress_fill_probability_sensitivity,
                tail_threshold=self.execution.tail_risk_threshold,
                tail_spread_multiplier=self.execution.tail_spread_multiplier,
                tail_impact_multiplier=self.execution.tail_impact_multiplier,
                tail_liquidity_multiplier=self.execution.tail_liquidity_multiplier,
                tail_fill_probability_floor=self.execution.tail_fill_probability_floor,
            )
        return DefaultExecutionHandler()

    def _fill_order(
        self, timestamp: pd.Timestamp, symbol: str, requested: float, bar: pd.Series
    ) -> Fill:
        context = HandlerContext(timestamp, symbol, requested, bar, self.rng)
        return self.handler.fill(context, self.execution)
