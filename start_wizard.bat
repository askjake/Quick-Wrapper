@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Missing project .venv. Run: py -3 -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0wizard.py"
if errorlevel 1 pause
