#!/bin/bash
# macOS/Linuxで使う場合の起動スクリプト（Windowsの人はrun.batを使ってください）
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "[初回セットアップ] 仮想環境を作成しています..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

echo
echo "=== スクリーナーを実行します ==="
python3 screener.py
STATUS=$?

if [ -f output/report.html ]; then
    if command -v open >/dev/null 2>&1; then
        open output/report.html
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open output/report.html
    fi
fi

exit $STATUS
