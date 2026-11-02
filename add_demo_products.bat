@echo off
setlocal
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
  echo Run start.bat first, then run this again.
  pause
  exit /b 1
)
venv\Scripts\python.exe manage.py add_demo_products
pause
