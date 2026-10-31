@echo off
if "%~1"=="" (
  echo Usage: eval_serial_vs_gt.bat ^<serial_log^> ^<images_dir^> ^<labels_dir^>
  pause
  exit /b 1
)
python "%~dp0eval_serial_vs_gt.py" %*
pause
