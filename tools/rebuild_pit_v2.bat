@echo off
cd /d "%~dp0"
if exist data\pit_v2\refresh_done.txt del data\pit_v2\refresh_done.txt
echo Rebuilding data\pit_v2 with the pre-2006 split fix (10-20 minutes)...
.venv\Scripts\python.exe tests\build_pit_v2.py data\bhavcopy\bhavcopy_equity.parquet data\pit_v2 > data\pit_v2\build.log 2>&1
echo %date% %time%> data\pit_v2\refresh_done.txt
echo DONE - you can close this window.
pause
