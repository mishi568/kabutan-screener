"""
株探のランキング系ページ（銘柄探検・株価注意報）の構造調査スクリプト
------------------------------------------------------------
やること：
  1. 指定したURLのHTMLを取得して生保存する（後で見返せるように）
  2. pandasでテーブル(<table>)を全部拾って、件数・列名・先頭数行を表示する
  3. どのテーブルが「本命のランキング表」かを目視で判断する材料にする

このスクリプト自体は1URLにつき1回しかリクエストしないので、
複数ページを調べたいときは URLS リストに追記して、
必ず数秒のインターバルを空けて実行してください（一度に全部叩かない）。
"""

import time
import pathlib
import requests
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://kabutan.jp/",
}

OUT_DIR = pathlib.Path("raw_html")
OUT_DIR.mkdir(exist_ok=True)

# 調べたいページ。まずはこの2つだけ。必要に応じて追加してください。
URLS = {
    "warning_stop_high": "https://kabutan.jp/warning/?mode=3_1",       # 本日のストップ高銘柄
    "tansaku_volume_up": "https://kabutan.jp/tansaku/?mode=2_0311",    # 出来高急増銘柄
}


def inspect(name: str, url: str):
    print("=" * 60)
    print(f"[{name}] GET {url}")
    resp = requests.get(url, headers=HEADERS, timeout=15)
    print(f"status_code: {resp.status_code}, length: {len(resp.text)}")

    # 生HTML保存（後で目視確認・セレクタ調査用）
    html_path = OUT_DIR / f"{name}.html"
    html_path.write_text(resp.text, encoding="utf-8")
    print(f"saved raw html -> {html_path}")

    if resp.status_code != 200:
        print("[NG] ステータス異常。中断。")
        return

    try:
        tables = pd.read_html(resp.text)
    except ValueError as e:
        print(f"[!] pandasでテーブルが見つかりませんでした: {e}")
        return

    print(f"[OK] {len(tables)} 個の<table>を検出")
    for i, df in enumerate(tables):
        print(f"--- table[{i}] shape={df.shape} ---")
        print("columns:", list(df.columns))
        print(df.head(3).to_string())
        print()


def main():
    for i, (name, url) in enumerate(URLS.items()):
        if i > 0:
            time.sleep(3)  # ページ間は必ず数秒空ける
        inspect(name, url)


if __name__ == "__main__":
    main()
