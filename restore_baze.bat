@echo off
set PGPASSWORD=postgres

set PG_RESTORE="C:\Program Files\PostgreSQL\15\bin\pg_restore.exe"
set HOST=localhost
set PORT=5433
set USER=postgres
set DB=mrkdb
set BACKUP_DIR=D:\backup

echo ========================================
echo    RESTORE POSTGRESQL BEKAPA
echo ========================================
echo Dostupni bekapi:
echo ----------------------------------------

:: Prikaz svih dostupnih fajlova sa putanjom YYYY\MM\DD
for /f "tokens=* delims=" %%F in ('dir /b /s "%BACKUP_DIR%\mrkdb.backup"') do (
    set FILEPATH=%%F
    call echo %%FILEPATH:%BACKUP_DIR%\=%%
)

echo ----------------------------------------
set /p DATUM=Unesite datum (yyyy-mm-dd) [Enter za poslednji bekap]: 

if "%DATUM%"=="" (
    :: Ako je prazno, uzmi poslednji bekap po datumu
    for /f "delims=" %%L in ('dir /b /s /o:-d "%BACKUP_DIR%\*\*\mrkdb.backup"') do (
        set FILE=%%L
        goto :found
    )
) else (
    set YYYY=%DATUM:~0,4%
    set MM=%DATUM:~5,2%
    set DD=%DATUM:~8,2%
    set FILE=%BACKUP_DIR%\%YYYY%\%MM%\%DD%\mrkdb.backup
)

:found
if exist "%FILE%" (
    echo Pokrecem restore sa fajla: %FILE%
    %PG_RESTORE% --host=%HOST% --port=%PORT% --username=%USER% ^
      --dbname=%DB% --verbose "%FILE%"
    echo ----------------------------------------
    echo Restore zavrsen uspesno.
) else (
    echo Greska: Fajl ne postoji!
    echo Ocekivana putanja: %FILE%
)

pause
