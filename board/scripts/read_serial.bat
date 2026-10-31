@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0read_serial.ps1" %*
echo.
pause
