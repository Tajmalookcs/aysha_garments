@echo off
setlocal
cd /d "%~dp0"
title Digital Invoicing backup

if not exist venv\Scripts\python.exe (
  echo Run start.bat first, then run this again.
  pause
  exit /b 1
)

set "DEFAULT=%USERPROFILE%\Documents\InvoicingBackups"
set "TARGET="
echo Where should the backup go? Use a USB drive or another safe place.
echo Press Enter to use %DEFAULT%
set /p "TARGET=Folder: "
if not defined TARGET set "TARGET=%DEFAULT%"
set "TARGET=%TARGET:"=%"

venv\Scripts\python.exe manage.py backup_data "%TARGET%"
if errorlevel 1 (
  echo.
  echo The backup did not finish. See the message above.
  pause
  exit /b 1
)
echo.
echo Keep this backup private. It holds client records and the key to the FBR token.
pause
