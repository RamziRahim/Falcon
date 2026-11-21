@echo off
rem Falcon: corporate actions (2000-2004 and Oct-Nov 2026), symbol changes and index history 2000->today.
rem Run from the Falcon project folder. Progress: data\pit_sources\extras_2026_11.log (ends with DONE).
cd /d "%~dp0"
echo Downloading corporate actions, symbol changes and index history (about 20-40 minutes) ...
.venv\Scripts\python.exe tests\download_extras_2026_11.py > data\pit_sources\extras_2026_11_console.log 2>&1
echo All done. You can close this window.
