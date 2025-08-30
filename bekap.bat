@echo off
set PGPASSWORD=postgres

:: Preuzimamo datum u formatu YYYYMMDD
for /f %%a in ('wmic os get localdatetime ^| find "."') do set ldt=%%a

set YYYY=%ldt:~0,4%
set MM=%ldt:~4,2%
set DD=%ldt:~6,2%

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
