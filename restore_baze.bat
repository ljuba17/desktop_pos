@echo off
set PGPASSWORD=postgres
set PG_RESTORE="C:\Program Files\PostgreSQL\15\bin\pg_restore.exe"
set HOST=localhost
set PORT=5433
set USER=postgres
set DB=mrkdb

set BACKUPDIR=D:\backup

echo ========================================
echo   RESTORE POSTGRESQL BEKAPA
echo ========================================
echo Dostupni datumi bekapa:
echo ----------------------------------------

for /d %%G in ("%BACKUPDIR%\*") do (
    for /d %%M in ("%%G\*") do (
        for /d %%D in ("%%M\*") do (
            echo   %%~nD%%~nM%%~nG
        )
    )
)

echo ----------------------------------------
set /p DATUM=Unesite datum (ddmmyyyy): 

set GODINA=%DATUM:6,4%
set MESEC=%DATUM:2,2%
set DAN=%DATUM:0,2%

set FILE=%BACKUPDIR%\%GODINA%\%MESEC%\%DAN%\mrkdb.backup

if exist "%FILE%" (
    echo Pokrecem restore sa fajla:
    echo %FILE%
    %PG_RESTORE% --host=%HOST% --port=%PORT% --username=%USER% ^
      --dbname=%DB% --verbose ^
      "%FILE%"
    echo ----------------------------------------
    echo Restore zavrsen uspesno.
) else (
    echo Greska: Fajl ne postoji!
    echo Ocekivana putanja: %FILE%
)
pause
