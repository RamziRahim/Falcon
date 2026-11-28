#!/bin/bash
# Waits for the delivery-history download to finish, then pushes the
# result to the paper-data branch as one parquet file per year (<100 MB each).
set -e
cd ~/falcon
while pgrep -f download_delivery.py >/dev/null; do sleep 60; done
tail -3 ~/logs/delivery_history.log
rm -rf ~/pdata
git clone -q --single-branch --depth 1 -b paper-data "$(git remote get-url origin)" ~/pdata
mkdir -p ~/pdata/delivery
~/venv/bin/python - <<'PY'
import os, pandas as pd
d = pd.read_parquet("data/delivery/delivery_equity.parquet")
out = os.path.expanduser("~/pdata/delivery")
for y, g in d.groupby(d["Date"].dt.year):
    g.to_parquet(f"{out}/delivery_{y}.parquet", index=False)
print("rows", len(d), d["Date"].min(), d["Date"].max(), d["Date"].nunique(), "days")
PY
cd ~/pdata
git add delivery
git -c user.name="falcon-paper" -c user.email="falcon-paper@localhost" commit -qm "Delivery history 2007-2026 (NSE MTO / sec_bhavdata_full)"
git push -q origin paper-data
echo PUSHED
