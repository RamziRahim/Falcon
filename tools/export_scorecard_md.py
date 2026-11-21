import json, csv, sys
D = "/tmp/claude-0/-home-claude/bc00d2b6-bc92-528f-ae68-d7180e4ca2f1/scratchpad/dash/"
rows = json.load(open(D + "strategies.json")); bench = json.load(open(D + "benchmarks.json"))
OUT = sys.argv[1]
def p(v, plus=True): return "—" if v is None else (f"{'+' if plus and v > 0 else ''}{v:.1f}%".replace("-", "−"))
def l(v): return "—" if v is None else f"₹{v:.1f} L"
def n(v): return "—" if v is None else f"{int(round(v)):,}"
def c(v): return "—" if v is None else f"{int(v)}/6"
def a(v): return "—" if v is None else f"{v:+.2f}%".replace("-", "−")
def esc(s): return str(s or "—").replace("|", "/")
b = {r["period"]: r for r in bench}
md = []
md.append("# Falcon Backtest Scorecard\n")
md.append(f"Every NSE equity buy strategy and variant tested for Falcon, 2008–2026, after Indian trading costs: **{len(rows)} rows**. "
          "Compiled 10 Nov 2026 from the result files in the Falcon repository (`data/*_result.txt`); each test's frozen rules and full write-up are in `docs/*_preregistration.md`.\n")
md.append("## Bottom line\n")
md.append("- No strategy passed all six checks in both decades.\n"
          "- **The one edge that held on every sample of stocks is monthly momentum** (top 20 by 12-month return excluding the last month, rebalanced monthly, 10% stop): about 23–26% a year in 2019–26 and 11–13% in 2008–17, on all stocks, half A and half B, but with worst drops of −33% to −41% (2019–26) and −59% (2008–17), and about −36% in 2018.\n"
          "- **Best balance: monthly momentum + Falcon Momentum (clean-close entry), half the capital each.** On the unseen half B: 16.1% / 12.4% a year, worst drops −31% / −36%, 5 of 6 checks in both decades. It missed its frozen adoption bar by 0.06 points of drawdown.\n"
          "- Chart-pattern entries, breakout-timing tricks, dip-buying, volume rules, fixed brackets and early profit-taking added nothing reliable; several looked good on half A and failed on half B.\n"
          f"- Benchmark Nifty 50: {b['2019-26']['nifty_cagr']}% a year in 2019–26 (worst drop {b['2019-26']['nifty_dd']}%), {b['2008-17']['nifty_cagr']}% in 2008–17 (worst drop {b['2008-17']['nifty_dd']}%), {b['2018']['nifty_cagr']}% in 2018. "
          f"Owning every stock in the list equally: {b['2019-26']['ew_cagr']}%, {b['2008-17']['ew_cagr']}%, {b['2018']['ew_cagr']}%.\n")
md.append(open("/tmp/claude-0/-home-claude/bc00d2b6-bc92-528f-ae68-d7180e4ca2f1/scratchpad/md_guide.md").read())
cols = ["Strategy", "Code", "Family", "Sample", "Entry", "Stop", "Target", "Market filter", "Max hold",
        "2019–26", "2008–17", "2018", "₹10 L → 19–26", "₹10 L → 08–17", "₹10 L → 2018", "Drop 19–26", "Drop 08–17",
        "Win 19–26", "Win 08–17", "Avg/trade 19–26", "Avg/trade 08–17", "Trades 19–26", "Trades 08–17", "Trades 2018",
        "Checks 19–26", "Checks 08–17", "Verdict", "Notes", "Test document"]
def vals(r):
    return [esc(r["name"]), esc(r.get("code")), r["family"], r["sample"], esc(r["entry"]), esc(r["stop"]), esc(r["target"]), esc(r["filter"]), esc(r["hold"]),
            p(r["cagr_w1"]), p(r["cagr_w2"]), p(r["cagr_y18"]), l(r["grew_w1"]), l(r["grew_w2"]), l(r["grew_y18"]),
            p(r["dd_w1"], False), p(r["dd_w2"], False), p(r["win_w1"], False), p(r["win_w2"], False), a(r["net_w1"]), a(r["net_w2"]),
            n(r["trades_w1"]), n(r["trades_w2"]), n(r["trades_y18"]), c(r["passes_w1"]), c(r["passes_w2"]), esc(r.get("verdict")), esc(r.get("note")), esc(r.get("doc"))]
md.append("## Final shortlist\n")
md.append("| # | " + " | ".join(cols) + " |\n|" + "---|" * (len(cols) + 1) + "\n")
for r in sorted([r for r in rows if r.get("top5")], key=lambda r: r["top5"]):
    md.append(f"| {r['top5']} | " + " | ".join(vals(r)) + " |\n")
order = ["All stocks", "Half A", "Half B", "Screener list"]
fam_order = ["Monthly momentum", "#3 Momentum breakout", "Falcon Momentum", "Portfolio combination", "Other"]
for smp in order:
    sub = [r for r in rows if r["sample"] == smp]
    if not sub: continue
    md.append(f"\n## All results — sample: {smp} ({len(sub)} rows)\n")
    if smp == "Half A": md.append("\nHalf-A figures are only comparable with other half-A rows.\n")
    for fam in fam_order:
        fr = sorted([r for r in sub if r["family"] == fam], key=lambda r: -(r["cagr_w1"] if r["cagr_w1"] is not None else -999))
        if not fr: continue
        md.append(f"\n### {fam} ({len(fr)})\n\n| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for r in fr: md.append("| " + " | ".join(vals(r)) + " |\n")
open(OUT + ".md", "w").write("".join(md))
with open(OUT + ".csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); keys = ["id", "name", "code", "family", "sample", "entry", "stop", "target", "filter", "hold"] + \
        [f"{k}_{t}" for k in ("cagr", "grew", "dd", "win", "net", "trades", "passes", "total") for t in ("w1", "w2", "y18")] + ["verdict", "note", "doc"]
    w.writerow(keys)
    for r in rows: w.writerow([r.get(k) for k in keys])
print("ok", len(rows))
