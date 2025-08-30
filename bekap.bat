@echo off
set PGPASSWORD=postgres

:: Preuzimamo datum
for /f "tokens=2-4 delims=/. " %%a in ('date /t') do (
    set DD=%%a
    set MM=%%b
    set YYYY=%%c
)

:: Putanja za bekap
set BACKUP_DIR=D:\backup\%YYYY%\%MM%\%DD%
set BACKUP_FILE=%BACKUP_DIR%\mrkdb.backup

:: Kreiramo foldere ako ne postoje
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: Pokrećemo pg_dump
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" ^
  --host=localhost --port=5433 --username=postgres ^
  --format=custom --file="%BACKUP_FILE%" ^
  mrkdb

echo Backup završen. Fajl: %BACKUP_FILE%
pause
