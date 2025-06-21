@echo off
echo ===============================
echo   Git commit automatizacija
echo ===============================
echo.

set /p COMMIT_MSG=Unesite poruku za commit: 

git add .
git commit -m "%COMMIT_MSG%"

echo.
echo ✅ Commit uspešno napravljen.
pause
