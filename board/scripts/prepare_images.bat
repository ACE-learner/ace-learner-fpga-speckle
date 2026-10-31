@echo off
set /p "L=SD card drive letter (e.g. F:): "
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_images.ps1" -DriveLetter %L%
echo.
pause
