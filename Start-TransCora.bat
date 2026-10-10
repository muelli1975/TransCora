@echo off
cd /d "%~dp0"
if exist "TransCora.exe" (
    start "" "TransCora.exe"
    exit /b
)
py -3 run_transcora.py
if errorlevel 1 pause
