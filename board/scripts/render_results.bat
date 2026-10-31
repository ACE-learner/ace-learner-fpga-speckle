@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0render_results.ps1" %*
echo.
pause
