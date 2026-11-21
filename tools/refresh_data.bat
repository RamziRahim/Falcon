@echo off
rem Falcon: (1) download corporate actions, symbol changes and index history,
rem (2) rebuild the PIT dataset 2000 -> latest into data\pit_v2 (data\pit is left untouched).
rem Run from the Falcon project folder. When finished, data\pit_v2\refresh_done.txt appears.
cd /d "%~dp0"
if exist data\pit_v2\refresh_done.txt del data\pit_v2\refresh_done.txt
echo Step 1 of 2: corporate actions, symbol changes, index history (about 20-40 minutes) ...
.venv\Scripts\python.exe tests\download_extras_2026_11.py > data\pit_sources\extras_2026_11_console.log 2>&1
echo Step 2 of 2: rebuilding adjusted prices and monthly lists (about 10-20 minutes) ...
if not exist data\pit_v2 mkdir data\pit_v2
.venv\Scripts\python.exe tests\build_pit_v2.py data\bhavcopy\bhavcopy_equity.parquet data\pit_v2 > data\pit_v2\build.log 2>&1
echo done > data\pit_v2\refresh_done.txt
echo All done. You can close this window.
