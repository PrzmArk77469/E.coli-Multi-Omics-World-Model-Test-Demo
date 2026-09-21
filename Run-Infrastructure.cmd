@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Resume-Infrastructure.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if "%EXIT_CODE%"=="0" (
    echo Infrastructure resume completed successfully.
) else (
    echo Infrastructure resume failed with exit code %EXIT_CODE%.
)
echo Logs: "%~dp0logs"
pause
exit /b %EXIT_CODE%
