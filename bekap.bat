@echo off
set PGPASSWORD=postgres
"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe" ^
  --host=localhost --port=5433 --username=postgres ^
  --format=custom --file="D:\backup\mrkdb.backup" ^
  mrkdb
echo Backup završen. Fajl: D:\backup\mrkdb.backup
pause