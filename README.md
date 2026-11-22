# Falcon paper-trading seed data

Inputs for `paper/data_update.py` on the Oracle server, as of the 2026-11-20 session.
Rebuild the bhavcopy with `cat data/bhavcopy/bhavcopy_equity.parquet.part* > data/bhavcopy/bhavcopy_equity.parquet`.
SHA256SUMS lists the reassembled bhavcopy and the laptop/cloud build outputs (data/pit_v2) the server's build must reproduce.

Content fingerprints of the reference build (python fingerprint.py, run from the repo root):
- data/pit_v2/prices_adjusted.parquet (10065923, 14) 41453629405132
- data/pit_v2/universe_monthly.parquet (158463, 5) 105416017382302
