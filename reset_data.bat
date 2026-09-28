@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo Neuro Coin database reset
echo ========================================
echo.
echo This will permanently delete the local database.
echo Type DELETE to confirm. Anything else will cancel.
echo.

set "CONFIRM_DELETE="
set /P "CONFIRM_DELETE=Confirmation: "

if not "%CONFIRM_DELETE%"=="DELETE" (
  echo.
  echo Cancelled. No data was deleted.
  pause
  goto end
)

echo.
echo Deleting database files...

if exist "data\neurocoin.db" del /F /Q "data\neurocoin.db"
if exist "data\neurocoin.db-shm" del /F /Q "data\neurocoin.db-shm"
if exist "data\neurocoin.db-wal" del /F /Q "data\neurocoin.db-wal"

echo.
echo Database reset complete.
pause

:end
endlocal
