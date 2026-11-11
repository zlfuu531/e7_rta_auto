@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Please run setup.bat first. Install Python 3.12 x64 if prompted.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0tools\launch_pc.py"
if errorlevel 1 pause
