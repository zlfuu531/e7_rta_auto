@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\setup_pc.ps1"
if errorlevel 1 (
    echo Setup failed. See the error above.
    pause
    exit /b 1
)
pause
