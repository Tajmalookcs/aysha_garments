@echo off
setlocal
cd /d "%~dp0"
title Digital Invoicing

if exist venv\Scripts\python.exe goto check_packages
echo First run: setting up. This needs internet and takes a few minutes.
py -3 -m venv venv
if exist venv\Scripts\python.exe goto check_packages
python -m venv venv
if exist venv\Scripts\python.exe goto check_packages
echo Python was not found. Install Python 3.12 or newer from python.org, then run this again.
pause
exit /b 1

:check_packages
venv\Scripts\python.exe -c "import django, whitenoise, waitress, requests, cryptography" >nul 2>&1
if not errorlevel 1 goto prepare
echo Installing the packages. This needs internet and takes a few minutes.
venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto install_failed
venv\Scripts\python.exe -c "import django, whitenoise, waitress, requests, cryptography" >nul 2>&1
if not errorlevel 1 goto prepare

:install_failed
echo The packages could not be installed. Check the internet connection, then run this again.
pause
exit /b 1

:prepare
venv\Scripts\python.exe manage.py migrate --noinput
if errorlevel 1 goto db_failed
venv\Scripts\python.exe manage.py collectstatic --noinput >nul
if errorlevel 1 goto db_failed

echo.
echo Digital Invoicing is running at http://127.0.0.1:8000
echo Keep this window open while using the app. Close it to stop the app.
start "" http://127.0.0.1:8000
venv\Scripts\python.exe -m waitress --listen=127.0.0.1:8000 config.wsgi:application
pause
exit /b 0

:db_failed
echo The app could not be prepared. See the message above.
pause
exit /b 1
