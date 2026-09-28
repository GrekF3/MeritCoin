@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=Neuro Coin"
if not defined NEURO_HOST set "NEURO_HOST=127.0.0.1"
if not defined NEURO_PORT set "NEURO_PORT=8017"
set "BROWSER_HOST=%NEURO_HOST%"
if /I "%BROWSER_HOST%"=="0.0.0.0" set "BROWSER_HOST=127.0.0.1"
set "SERVER_URL=http://%BROWSER_HOST%:%NEURO_PORT%"

echo ========================================
echo %APP_NAME% first setup
echo ========================================
echo.

if not exist "data" mkdir "data"

if not exist ".venv" (
  echo Creating Python virtual environment...
  py -3.12 -m venv .venv
  if errorlevel 1 py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
  if errorlevel 1 goto error
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto error

echo Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto error

python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo Applying database migrations...
alembic upgrade head
if errorlevel 1 goto error

echo.
choice /C YN /D Y /T 15 /M "Create demo data? Default is Y"
if errorlevel 2 goto custom_admin
if errorlevel 1 goto demo_data

:demo_data
echo.
echo Creating demo data...
python -m app.db.init_db --demo
if errorlevel 1 goto error
echo.
echo Demo accounts:
echo   Admin: admin / admin
echo   Student: student / student
goto launch_server

:custom_admin
echo.
echo Demo data will not be created.
call :ask_admin
if errorlevel 1 goto error

:launch_server
echo.
echo Server URL: %SERVER_URL%
echo The browser will open after the server is ready.
start "" /B python -m app.db.open_when_ready "%SERVER_URL%"
echo.
echo Press Ctrl+C to stop the server.
echo This window will stay open after the server stops.
echo.

uvicorn app.main:app --host "%NEURO_HOST%" --port "%NEURO_PORT%"
if errorlevel 1 goto error

echo.
echo Server stopped.
pause
goto end

:ask_admin
python -m app.db.init_db --has-admin >nul 2>nul
if not errorlevel 1 (
  echo Admin account already exists.
  exit /B 0
)

echo.
echo No admin account found. Create one now.

:ask_admin_username
set "ADMIN_USERNAME="
set /P "ADMIN_USERNAME=Admin username: "
if "%ADMIN_USERNAME%"=="" (
  echo Admin username cannot be empty.
  goto ask_admin_username
)

:ask_admin_password
set "ADMIN_PASSWORD="
set /P "ADMIN_PASSWORD=Admin password: "
if "%ADMIN_PASSWORD%"=="" (
  echo Admin password cannot be empty.
  goto ask_admin_password
)

python -m app.db.init_db --admin "%ADMIN_USERNAME%" --admin-password "%ADMIN_PASSWORD%"
if errorlevel 1 exit /B 1

echo.
echo Admin account:
echo   %ADMIN_USERNAME% / %ADMIN_PASSWORD%
exit /B 0

:error
echo.
echo Failed to start Neuro Coin. Check the error above.
pause

:end
endlocal
