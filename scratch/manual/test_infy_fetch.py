from market_data.data_collection_engine import DataCollectionEngine
from technical_analysis.indicator_engine import IndicatorEngine

fix = ["INFY.NS"]
DataCollectionEngine().run(symbols=fix)
IndicatorEngine().run(symbols=fix)