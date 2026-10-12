@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo 請先安裝 Python 3.11，並勾選 Python Launcher。
    pause
    exit /b 1
  )
)
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 (
  echo 依賴安裝失敗，請保留錯誤訊息以便診斷。
  pause
  exit /b 1
)
.venv\Scripts\python.exe app.py
if errorlevel 1 pause
