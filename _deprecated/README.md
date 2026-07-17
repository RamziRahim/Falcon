# Deprecated / Quarantined Files

Moved out of the active codebase during cleanup (2026-07-15, reapplied after
reconciling with the scoring engine build).

- **app_old.py** — superseded by root `app.py`.
- **market_data/data_validator_old.py** — superseded by `market_data/data_validator.py`.
- **run_pipeline.py** — references a `scripts/` folder and files that don't exist
  anywhere in this project (leftover from before the package refactor). Will fail
  immediately if run. Nothing imports it.

Nothing was permanently deleted — review and delete this folder once confirmed safe.
