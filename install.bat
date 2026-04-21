@echo off
REM Jednorazowa instalacja wszystkich bibliotek.
cd /d "%~dp0"

echo ====================================================
echo   Vinted Manager - Instalacja bibliotek
echo ====================================================
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo ====================================================
echo   Gotowe! Mozesz uruchomic start_all.bat
echo ====================================================
pause
