# Falcon paper-trading records

Written only by the Oracle server (`paper/server/run_daily.sh`): after each daily run it copies
`paper/ledger`, `paper/orders`, `paper/reports` and `paper/state.json` here and commits them,
so every day of the frozen paper-trading plan (`docs/paper_trading_plan.md`) has a dated record.
