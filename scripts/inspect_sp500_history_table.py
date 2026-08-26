from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

URL = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"
response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0 Inhibit research"}, timeout=30)
tables = pd.read_html(StringIO(response.text))
for index, table in enumerate(tables):
    print(index, table.shape, table.columns.tolist())
    if "Effective Date" in str(table.columns):
        print(table.head(3).to_string())
