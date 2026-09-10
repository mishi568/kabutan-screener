@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install it from https://www.python.org/
    echo ^(Check "Add Python to PATH" during installation.^)
    pause
    exit /b 1
)

if not exist venv (
    echo [First run] Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Checking dependencies...
pip install -q -r requirements.txt

if not exist venv\.playwright_chromium_installed (
    echo.
    echo [First run] Downloading Chromium for Playwright (about 150-300MB, one time only)...
    python -m playwright install chromium
    if errorlevel 1 (
        echo Failed to download Chromium. Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo done > venv\.playwright_chromium_installed
)

echo.
echo === Running volume watch ===
python volume_watch.py %*
set WATCH_EXIT=%errorlevel%

if exist output\volume_report.html (
    start "" "output\volume_report.html"
)

echo.
if %WATCH_EXIT% neq 0 (
    echo An error occurred. Please check the log above.
) else (
    echo Done. Paste output\volume_summary_latest.json into your chat with Claude to get comments.
)
pause
