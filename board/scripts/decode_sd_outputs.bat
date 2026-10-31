@echo off
if "%~1"=="" (
  echo Usage: decode_sd_outputs.bat ^<yolo_test_dir^> ^<images_dir^> ^<output_dir^>
  pause
  exit /b 1
)
python "%~dp0decode_sd_outputs.py" %*
pause
