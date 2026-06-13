@echo off
setlocal
echo ==========================================
echo ATP DATA LOCAL UPDATE V36
echo ==========================================
echo.
set /p MODE=Wpisz tryb [live/full] (domyslnie live): 
if "%MODE%"=="" set MODE=live
set UPDATE_MODE=%MODE%
set ATP_USE_PLAYWRIGHT=1

python --version
if errorlevel 1 (
    echo Nie znaleziono Pythona. Zainstaluj Python 3.11+ i zaznacz Add Python to PATH.
    pause
    exit /b 1
)

pip install -r requirements.txt
python -m playwright install chromium
python scripts\update_atp.py

echo.
echo Jesli jest OK:
echo git add data
echo git commit -m "Update ATP data local"
echo git push
echo.
pause
