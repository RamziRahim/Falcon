@echo off
rem Falcon: download NSE daily bhavcopies (resumable; finished days are skipped).
rem 1) 2 Nov - 20 Nov 2026, to bring prices up to date for paper trading
rem 2) 2000 - 2006, to extend the backtest history
rem Logs go to data\bhavcopy\. When both are done, data\bhavcopy\dl_done.txt appears.
rem Run from the Falcon project folder (the folder that holds this file).
cd /d "%~dp0"
if exist data\bhavcopy\dl_done.txt del data\bhavcopy\dl_done.txt
echo Downloading 2-20 Nov 2026 ...
.venv\Scripts\python.exe tests\download_bhavcopies.py 2026-11-02 2026-11-20 > data\bhavcopy\dl_nov2026.log 2>&1
echo Downloading 2000-2006 (30-60 minutes) ...
.venv\Scripts\python.exe tests\download_bhavcopies.py 2000-01-01 2006-12-31 > data\bhavcopy\dl_2000_2006.log 2>&1
echo done > data\bhavcopy\dl_done.txt
echo All done. You can close this window.
