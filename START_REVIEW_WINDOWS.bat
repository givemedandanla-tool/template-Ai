@echo off
setlocal
set "PYTHONUTF8=1"
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo 尚未完成首次準備。請先執行 PREPARE_WINDOWS.bat。
  echo 這個入口只啟動作品判讀工具，不會下載或安裝套件。
  pause
  exit /b 2
)
.venv\Scripts\python.exe tools\local_start.py --check
if errorlevel 1 (
  echo 作品判讀工具尚未啟動。請依上方說明修復環境後重試。
  pause
  exit /b 2
)
rem A separate pythonw process owns the GUI; this temporary command window exits.
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0review_app.py" %*
exit /b %errorlevel%
