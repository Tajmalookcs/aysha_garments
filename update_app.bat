@echo off
setlocal
cd /d "%~dp0"
title Update Digital Invoicing
echo Checking for an update. This needs internet.
echo.
set PY=venv\Scripts\python.exe
if not exist %PY% set PY=py -3
%PY% update_app.py
if errorlevel 1 goto failed
echo.
echo Opening the app.
start "" wscript "%~dp0start_app.vbs"
echo.
pause
exit /b 0

:failed
echo.
echo The update didn't finish. The app was not changed.
pause
exit /b 1
