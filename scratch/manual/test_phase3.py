import pandas as pd

from market_data.data_collection_engine import (
    market_data_engine,
)

watchlist = pd.read_excel(
    "master_watchlist.xlsx"
)

symbols = watchlist["Symbol"].tolist()

result = market_data_engine.run(symbols)

print(result)