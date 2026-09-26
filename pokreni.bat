@echo off
cd /d "%~dp0"

py uskladi_godinu.py
if errorlevel 1 (
    echo.
    echo POS nije pokrenut jer provera poslovne godine nije uspela.
    pause
    exit /b 1
)

echo.
py desktop_main.py
echo.