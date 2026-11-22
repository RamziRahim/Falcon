@echo off
cd /d "%~dp0"
if not exist data\pit_v2 mkdir data\pit_v2
echo Updating NSE data for paper trading (10-20 minutes)...
.venv\Scripts\python.exe paper\data_update.py > data\pit_v2\paper_update_console.log 2>&1
echo DONE - you can close this window.
pause
