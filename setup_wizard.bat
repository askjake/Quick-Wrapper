@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
"%~dp0.venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
"%~dp0.venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto fail
echo Wizard environment ready. Run start_wizard.bat
exit /b 0
:fail
echo Setup failed. Inspect the error above; do not deploy.
pause
exit /b 1
