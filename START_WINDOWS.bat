@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo 尚未完成首次準備。請先執行 PREPARE_WINDOWS.bat，或查看本機快速開始文件。
  echo 這次啟動不會下載或安裝任何套件。
  pause
  exit /b 2
)
.venv\Scripts\python.exe tools\local_start.py %*
set "TEMPLATE_AI_EXIT=%errorlevel%"
if not "%TEMPLATE_AI_EXIT%"=="0" pause
exit /b %TEMPLATE_AI_EXIT%
