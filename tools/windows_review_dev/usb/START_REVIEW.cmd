@echo off
setlocal
chcp 65001 >nul
if not exist "%~dp0python\python.exe" (
  echo Missing offline Python. Copy the complete ReviewTool-USB folder, not this file alone.
  pause
  exit /b 2
)
"%~dp0python\python.exe" -I -B "%~dp0source\tools\windows_review_dev\usb\offline_start.py" --bundle "%~dp0." %*
set "review_result=%errorlevel%"
if not "%review_result%"=="0" pause
exit /b %review_result%
