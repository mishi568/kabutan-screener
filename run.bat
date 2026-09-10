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

echo.
echo === Running screener ===
python screener.py %*
set SCREENER_EXIT=%errorlevel%

if exist output\report.html (
    start "" "output\report.html"
)

echo.
if %SCREENER_EXIT% neq 0 (
    echo An error occurred. Please check the log above.
) else (
    echo Done. Paste output\summary_latest.json into your chat with Claude to get comments.
)
pause
