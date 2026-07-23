import pandas as pd

df = pd.read_parquet("data/raw/BSE.NS.parquet")

print(df.tail())