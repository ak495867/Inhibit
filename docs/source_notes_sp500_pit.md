# S&P 500 Point-in-Time Source Notes

The current constituent source is the Wikipedia list of S&P 500 companies: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies. The historical change source is https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500.

The historical-components page contains dated effective additions and removals, including recent rows such as HUBB replacing OGN on 2023-10-18, and many earlier change events. It states that S&P Dow Jones Indices updates components periodically in response to mergers, spin-offs, and quarterly rebalancing. This table can be converted into effective membership intervals, but it is not an official licensed historical constituent feed and must be treated as a research-source snapshot with provenance and review.

Point-in-time membership means a symbol is eligible on date t only if its addition effective date is on or before t and its removal effective date is after t. A current-constituent backtest applied to earlier years has survivorship bias; the requested comparison should therefore retain both the current-snapshot and historical-membership results, label their source and limitations, and not claim the free table is equivalent to an official index-vintage database.
