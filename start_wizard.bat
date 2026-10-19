@echo off
cd /d "%~dp0"
py -3 wizard.py
if errorlevel 1 pause
