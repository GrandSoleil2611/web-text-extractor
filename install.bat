@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo  Web Text Extractor Final - Installer
echo ========================================

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Khong tim thay Python trong PATH.
    echo Cai Python 3.11/3.12 va tick Add Python to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Tao virtual environment...
    python -m venv .venv
    if errorlevel 1 goto :fail
) else (
    echo [1/4] .venv da ton tai.
)

echo [2/4] Nang cap pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [3/4] Cai dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [4/4] Cai Chromium cho Playwright...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :fail

echo.
echo Cai dat thanh cong.
echo Chay run.bat de mo tool.
pause
exit /b 0

:fail
echo.
echo [ERROR] Cai dat that bai. Xem log phia tren.
pause
exit /b 1
