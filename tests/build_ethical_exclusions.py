"""
Falcon -- classify every stock that was ever in the monthly top-500 (data/pit_v2) against
Falcon's live sector rules (config.EXCLUDED_SECTORS, EXCLUDED_TICKERS, FAIL_INDUSTRY_KEYWORDS):
financial services, alcohol and tobacco. Debt-to-equity is NOT applied (no history).
See docs/ethical_filter_history_preregistration.md.

Order of evidence for each stock (first match decides):
  1. ticker in config.EXCLUDED_TICKERS (alcohol, hand-verified), or in
     HAND_EXCLUDE (reviewed by hand before freeze)                         -> exclude
  2. data/sector_map.json (Yahoo): sector in EXCLUDED_SECTORS, or industry
     containing a FAIL_INDUSTRY_KEYWORD                                    -> exclude, else keep
  3. company name (NSE corporate-action records) matching NAME_RULES       -> exclude
  4. otherwise                                                             -> keep (no evidence)

    python tests/build_ethical_exclusions.py
Writes data/pit_v2/ethical_exclusions.csv.
"""
import sys
sys.path.insert(0, ".")

import glob
import json
import re

import pandas as pd

import config

# whole-word company-name patterns (case-insensitive)
NAME_RULES = {
    "financial": [r"\bbank\b", r"\bbanking\b", r"\bfinance\b", r"\bfinancial\b", r"\bfinancials\b", r"\bfinserv\b",
                  r"\bfinvest\b", r"\bfincorp\b", r"\bfincap\b", r"\binsurance\b", r"\bassurance\b", r"\bcredit\b",
                  r"\bleasing\b", r"\bsecurities\b", r"\bbroking\b", r"\bstock ?broking\b", r"\basset management\b",
                  r"\bhousing finance\b", r"\bmicrofinance\b", r"\bcapital (?:ltd|limited)\b", r"\binvestments? (?:ltd|limited)\b",
                  r"\bexchange (?:ltd|limited)\b", r"\bdepository\b", r"\bnbfc\b",
                  r"\bstock ?brokers?\b", r"\bshare (?:and|&) stock\b", r"\bcapital (?:first|advisors|services)\b",
                  r"\binvestdirect\b", r"\binvestment managers\b", r"\bcreditcare\b", r"\bmoney (?:ltd|limited)\b"],
    "alcohol": [r"\bbrewer(?:y|ies)\b", r"\bdistiller(?:y|ies)\b", r"\bspirits\b", r"\bwines?\b", r"\bvineyards?\b",
                r"\bliquors?\b", r"\balco", r"\bspirit (?:ltd|limited)\b"],
    "tobacco": [r"\btobacco\b", r"\bcigarettes?\b"],
}


# reviewed by hand before freeze (name rule would misfire): kept despite a matching word
NAME_OVERRIDE_KEEP = {"NETWORK18"}       # Network18 Media & Investments: a media company
# reviewed by hand before freeze: no sector record and the name rule misses them
HAND_EXCLUDE = {
    "MCDOWELL": "alcohol",      # McDowell & Company (United Spirits' predecessor)
    "RADICOKHAI": "alcohol",    # Radico Khaitan, earlier listing
    "JAGAJITIND": "alcohol",    # Jagatjit Industries (distiller)
    "VSTIND": "tobacco",        # VST Industries (cigarettes)
    "NORTHARC": "financial",    # Northern Arc Capital (NBFC)
    "KISSHT": "financial",      # OnEMI / Kissht (digital lender)
    "MORGANSTAN": "financial",  # Morgan Stanley Growth Fund (listed mutual fund, 2000-08)
}


def name_rule(name: str):
    n = str(name).lower()
    for group, pats in NAME_RULES.items():
        for p in pats:
            if re.search(p, n):
                return group, p
    return None


def main():
    uni = pd.read_parquet("data/pit_v2/universe_monthly.parquet")
    ents = set(uni["entity_id"].unique())
    px = pd.read_parquet("data/pit_v2/prices_adjusted.parquet", columns=["entity_id", "Symbol", "current_symbol"]).drop_duplicates()
    px = px[px["entity_id"].isin(ents)]
    syms = px.groupby("entity_id").apply(lambda d: sorted(set(d["Symbol"]) | set(d["current_symbol"])), include_groups=False)
    current = px.groupby("entity_id")["current_symbol"].last()

    ca = pd.concat([pd.read_parquet(f, columns=["symbol", "comp", "exDate"]) for f in
                    glob.glob("data/pit_sources/corporate_actions_*.parquet") + ["data/corporate_actions_cache.parquet"]])
    names = ca.dropna(subset=["comp"]).groupby("symbol")["comp"].last()
    smap = {k.replace(".NS", ""): v for k, v in json.load(open("data/sector_map.json")).items()}
    alcohol = {t.replace(".NS", "") for t in config.EXCLUDED_TICKERS}
    fail_kw = [k.lower() for k in config.FAIL_INDUSTRY_KEYWORDS]
    bad_sectors = set(config.EXCLUDED_SECTORS)

    rows = []
    for e, ss in syms.items():
        nm = next((names[s] for s in reversed(ss) if s in names.index), "")
        rec = next((smap[s] for s in reversed(ss) if s in smap and smap[s].get("sector") not in ("Unknown", "")), None)
        if set(ss) & alcohol:
            out, group, source = True, "alcohol", "config.EXCLUDED_TICKERS"
        elif set(ss) & set(HAND_EXCLUDE):
            out, group, source = True, HAND_EXCLUDE[sorted(set(ss) & set(HAND_EXCLUDE))[0]], "hand-reviewed list"
        elif rec is not None:
            ind = str(rec.get("industry", "")).lower()
            hit = next((k for k in fail_kw if k in ind), None)
            if rec["sector"] in bad_sectors:
                out, group, source = True, "financial", f"sector_map: {rec['sector']} / {rec.get('industry')}"
            elif hit:
                out = True
                group = "tobacco" if hit == "tobacco" else "alcohol" if hit in ("wineries", "distilleries") else "financial"
                source = f"sector_map industry: {rec.get('industry')}"
            else:
                out, group, source = False, "", f"sector_map: {rec['sector']} / {rec.get('industry')}"
        else:
            r = name_rule(nm) if nm and current[e] not in NAME_OVERRIDE_KEEP else None
            if r:
                out, group, source = True, r[0], f"name matches {r[1]}"
            else:
                out, group, source = False, "", "name, no match" if nm else "no name found"
        rows.append({"entity_id": e, "current_symbol": current[e], "symbols": "|".join(ss), "name": nm,
                     "excluded": out, "group": group, "source": source})
    df = pd.DataFrame(rows).sort_values(["excluded", "group", "current_symbol"], ascending=[False, True, True])
    df.to_csv("data/pit_v2/ethical_exclusions.csv", index=False)

    uni["month_end"] = pd.to_datetime(uni["month_end"])
    ex = set(df.loc[df["excluded"], "entity_id"])
    print(f"{len(df)} stocks ever in the top 500; excluded {len(ex)}:", df[df.excluded].group.value_counts().to_dict())
    print("evidence:", df["source"].str.split(":").str[0].str.replace(r"name matches.*", "name rule", regex=True).value_counts().to_dict())
    for y in (2001, 2004, 2008, 2012, 2016, 2020, 2024, 2026):
        m = uni[uni["month_end"].dt.year == y]
        print(f"  {y}: {100 * m['entity_id'].isin(ex).mean():.1f}% of top-500 member-months excluded")


if __name__ == "__main__":
    main()
