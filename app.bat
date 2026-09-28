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
echo %APP_NAME% app launcher
echo ========================================
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo The application is not installed yet.
  echo Please run start.bat first to install dependencies and prepare the database.
  pause
  goto end
)

if not exist "data\neurocoin.db" (
  echo Database was not found.
  echo Please run start.bat first to install dependencies and prepare the database.
  pause
  goto end
)

call .venv\Scripts\activate.bat
if errorlevel 1 goto error

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

:error
echo.
echo Failed to start Neuro Coin. Check the error above.
pause

:end
endlocal
