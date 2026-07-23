# Manual scripts

One-off scripts used for manual ticker debugging, data spot-checks, and early
phase smoke tests. None of these contain real `pytest` test functions -- they
were named `test_*.py` and living in `tests/`, which made pytest collect and
*execute* their top-level code (network calls, hardcoded-path file reads) on
every test run. Kept here for reference; run individually and manually if
needed, not as part of the automated suite.
