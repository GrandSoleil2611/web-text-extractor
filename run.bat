@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Chua co .venv. Hay chay install.bat truoc.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py
pause
