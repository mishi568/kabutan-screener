@echo off
setlocal

cd /d %~dp0

echo ==== Starting Kabutan Screener Dashboard ====
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python and add it to PATH.
    echo.
    pause
    exit /b 1
)

echo Checking dependencies (this may take a moment on first run)...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    echo.
    pause
    exit /b 1
)

echo.
echo Your browser will open at http://localhost:8501
echo To stop the app, press Ctrl+C in this window.
echo.

python -m streamlit run app.py

echo.
echo ==== App stopped ====
pause
