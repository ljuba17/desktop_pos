@echo off
set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe" ^
  --host=localhost --port=5433 --username=postgres ^
  --dbname=mrkdb --verbose ^
  "E:\backup\mrkdb.backup"
echo Restore završen.
pause