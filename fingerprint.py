import sys, pandas as pd
for f in ["data/pit_v2/prices_adjusted.parquet","data/pit_v2/universe_monthly.parquet"]:
    d=pd.read_parquet(f); d=d.sort_values(list(d.columns[:2])).reset_index(drop=True)
    print(f, d.shape, int(pd.util.hash_pandas_object(d,index=False).sum()) & 0xFFFFFFFFFFFF)
