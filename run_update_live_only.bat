@echo off
cd /d "%~dp0"
set UPDATE_MODE=live
set ATP_USE_PLAYWRIGHT=1
set SAVE_DEBUG_HTML=0
set ATP_CF_WAIT_SECONDS=75
python scripts\update_atp.py
pause
