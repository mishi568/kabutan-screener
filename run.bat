@echo off
setlocal
cd /d %~dp0

where python >nul 2>nul
if errorlevel 1 (
    echo Pythonが見つかりません。https://www.python.org/ からインストールしてください。
    pause
    exit /b 1
)

if not exist venv (
    echo [初回セットアップ] 仮想環境を作成しています...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo 依存パッケージを確認しています...
pip install -q -r requirements.txt

echo.
echo === スクリーナーを実行します ===
python screener.py
set SCREENER_EXIT=%errorlevel%

if exist output\report.html (
    start "" "output\report.html"
)

echo.
if %SCREENER_EXIT% neq 0 (
    echo 実行中にエラーが発生しました。上記のログを確認してください。
) else (
    echo 完了しました。output\summary_latest.json をClaudeとの会話に貼って確認を依頼できます。
)
pause
