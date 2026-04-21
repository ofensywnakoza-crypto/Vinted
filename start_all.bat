@echo off
REM Uruchamia wszystkie 3 skladniki Vinted Manager w osobnych oknach.
cd /d "%~dp0"

echo Uruchamiam aplikacje Vinted Manager...
echo.

start "Vinted Sync Server" cmd /k "python sync_server.py"
timeout /t 2 /nobreak >nul

start "Vinted Scheduler" cmd /k "python scheduler_runner.py"
timeout /t 2 /nobreak >nul

start "Vinted App" cmd /k "python -m streamlit run app.py"

echo.
echo Wszystko uruchomione.
echo - Aplikacja:  http://localhost:8501
echo - Synchronizacja: http://127.0.0.1:8765
echo - Scheduler:  dziala w tle
echo.
pause
