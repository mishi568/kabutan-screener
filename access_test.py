"""
株探(kabutan.jp)へのアクセス確認スクリプト
------------------------------------------------
目的：
  1. 通常のブラウザとして自然なヘッダーを付けてアクセスできるか確認する
  2. ページの構造（HTMLの一部）をざっと確認する

注意（マナー）：
  - このスクリプトは1回だけリクエストを送るテスト用です。
  - 複数銘柄・複数ページを取得する本番用スクレイパーでは、
    必ずリクエスト間に数秒のインターバルを入れてください。
  - 高頻度・並列アクセスはしないでください（利用規約で禁止されています）。
"""

import re
import sys
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://kabutan.jp/",
}

# トヨタ自動車(7203)のページでテスト
TEST_URL = "https://kabutan.jp/stock/?code=7203"


def main():
    print(f"GET {TEST_URL}")
    try:
        resp = requests.get(TEST_URL, headers=HEADERS, timeout=15)
    except requests.exceptions.RequestException as e:
        print(f"[NG] リクエスト自体が失敗しました: {e}")
        sys.exit(1)

    print(f"status_code : {resp.status_code}")
    print(f"content-type: {resp.headers.get('Content-Type')}")
    print(f"body length : {len(resp.text)} chars")

    title_match = re.search(r"<title>(.*?)</title>", resp.text, re.S)
    title = title_match.group(1).strip() if title_match else "(取得できず)"
    print(f"<title>     : {title}")

    # ボット判定ページ(Cloudflare等)によくある文言をざっくりチェック
    suspicious_markers = ["Attention Required", "Access denied", "Just a moment",
                           "cf-browser-verification", "captcha"]
    hit = [m for m in suspicious_markers if m.lower() in resp.text.lower()]
    if resp.status_code != 200:
        print("[NG] ステータスコードが200以外です。ブロックされている可能性があります。")
    elif hit:
        print(f"[NG] ボット検知ページの可能性があります（検出語: {hit}）。")
    elif "7203" not in resp.text and "トヨタ" not in resp.text:
        print("[?] 200は返っていますが、期待したページ内容ではないかもしれません。")
    else:
        print("[OK] 正常にページを取得できていそうです。")


if __name__ == "__main__":
    main()