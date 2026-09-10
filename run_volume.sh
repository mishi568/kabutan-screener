#!/bin/bash
# macOS/Linuxで使う場合の起動スクリプト（Windowsの人はrun_volume.batを使ってください）
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "[初回セットアップ] 仮想環境を作成しています..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f venv/.playwright_chromium_installed ]; then
    echo
    echo "[初回セットアップ] PlaywrightのChromiumをダウンロードしています（150〜300MB程度、初回のみ）..."
    python3 -m playwright install chromium
    echo "done" > venv/.playwright_chromium_installed
fi

echo
echo "=== 出来高急増ウォッチを実行します ==="
python3 volume_watch.py "$@"
STATUS=$?

if [ -f output/volume_report.html ]; then
    if command -v open >/dev/null 2>&1; then
        open output/volume_report.html
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open output/volume_report.html
    fi
fi

exit $STATUS
