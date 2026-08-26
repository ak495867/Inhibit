from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def build_fixture(days: int = 1700, symbols: int = 25) -> pd.DataFrame:
    dates = pd.date_range("2017-01-03", periods=days, freq="B", tz="UTC")
    records: list[dict[str, object]] = []
    for symbol_id in range(symbols):
        symbol = f"V{symbol_id:02d}"
        base = 30.0 + symbol_id
        time_index = np.arange(days, dtype=float)
        periodic = 0.0003 * np.sin(time_index / (13.0 + symbol_id))
        drift = 0.00005 * (symbol_id - symbols / 2)
        close = base * np.exp(np.cumsum(drift + periodic))
        volume = 150_000 + symbol_id * 8_000 + 20_000 * (1 + np.cos(time_index / 19.0))
        book_equity = close * (10.0 + symbol_id * 0.2)
        net_income = book_equity * (0.04 + 0.002 * np.sin(time_index / 31.0))
        market_cap = close * (100.0 + symbol_id * 2.0)
        for timestamp, price, traded_volume, book, income, market_value in zip(
            dates, close, volume, book_equity, net_income, market_cap, strict=True
        ):
            records.append(
                {
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "open": price * 0.999,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": traded_volume,
                    "adj_close": price,
                    "currency": "USD",
                    "available_at": timestamp,
                    "book_equity": book,
                    "net_income": income,
                    "market_cap": market_value,
                    "source": "inhibit-verification-fixture",
                }
            )
    return pd.DataFrame(records)


if __name__ == "__main__":
    output = Path("data/custom_verification_prices.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    build_fixture().to_csv(output, index=False)
    print(f"wrote {len(build_fixture())} rows to {output}")
