from __future__ import annotations

import pandas as pd

from inhibit.data.membership import apply_point_in_time_membership, load_membership


def test_point_in_time_membership_applies_effective_intervals(tmp_path) -> None:
    membership_path = tmp_path / "membership.csv"
    membership_path.write_text(
        "symbol,effective_from,effective_to\n"
        "AAA,2020-01-01,2020-06-01\n"
        "AAA,2020-06-01,\n"
        "BBB,2020-03-01,\n"
    )
    membership = load_membership(membership_path)
    prices = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "BBB", "BBB"],
            "timestamp": pd.to_datetime(
                ["2020-02-01", "2020-06-01", "2020-02-01", "2020-04-01"], utc=True
            ),
            "close": [10.0, 11.0, 20.0, 21.0],
        }
    )
    filtered, audit = apply_point_in_time_membership(prices, membership)
    assert filtered[["symbol", "timestamp"]].astype(str).to_dict("records") == [
        {"symbol": "AAA", "timestamp": "2020-02-01 00:00:00+00:00"},
        {"symbol": "AAA", "timestamp": "2020-06-01 00:00:00+00:00"},
        {"symbol": "BBB", "timestamp": "2020-04-01 00:00:00+00:00"},
    ]
    assert audit["membership_removed_rows"] == 1
