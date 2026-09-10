@echo off
setlocal
set LOG=%~dp0diagnose_log.txt

echo ==== diagnose.bat started ==== > "%LOG%"
echo step 0: batch started >> "%LOG%"

chcp 65001 >nul 2>>"%LOG%"
echo step 1: after chcp, errorlevel=%errorlevel% >> "%LOG%"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo step 2: env vars set >> "%LOG%"

cd /d %~dp0
echo step 3: after cd, CD=%CD% >> "%LOG%"

echo step 4: checking python location >> "%LOG%"
where python >>"%LOG%" 2>&1
echo step 4b: where python errorlevel=%errorlevel% >> "%LOG%"

echo step 5: checking python version >> "%LOG%"
python --version >>"%LOG%" 2>&1
echo step 5b: python --version errorlevel=%errorlevel% >> "%LOG%"

if not exist venv (
    echo step 6: venv missing, creating... >> "%LOG%"
    python -m venv venv >>"%LOG%" 2>&1
    echo step 6b: venv creation errorlevel=%errorlevel% >> "%LOG%"
) else (
    echo step 6: venv already exists >> "%LOG%"
)

echo step 7: activating venv >> "%LOG%"
call venv\Scripts\activate.bat >>"%LOG%" 2>&1
echo step 7b: after activate, errorlevel=%errorlevel% >> "%LOG%"

echo step 8: installing dependencies (this can take a while the first time) >> "%LOG%"
pip install -r requirements.txt >>"%LOG%" 2>&1
echo step 8b: pip install errorlevel=%errorlevel% >> "%LOG%"

echo step 9: reached end of diagnose script >> "%LOG%"

echo.
echo Diagnostics finished. A file named diagnose_log.txt was created
echo in this same folder. Please open it (double-click it, it opens
echo in Notepad) and paste its full contents into the chat with Claude.
echo.
pause
