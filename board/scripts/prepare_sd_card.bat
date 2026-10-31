@echo off
set /p "L=SD card drive letter (e.g. F:): "
set /p "R=Type YES to replace existing files: "
set "A=-DriveLetter %L%"
if /I "%R%"=="YES" set "A=%A% -ReplaceExisting"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare_sd_card.ps1" %A%
echo.
pause
