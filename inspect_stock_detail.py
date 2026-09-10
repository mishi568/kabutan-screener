# -*- coding: utf-8 -*-
"""
個別銘柄ページ（kabutan.jp/stock/?code=XXXX）の表構造を調査するスクリプト。

このページには「業績推移」「信用取引（週次）」など複数の<table>が
入り組んでいるので、まずどのtable[i]が何に対応するかを確認する。

使い方:
  python inspect_stock_detail.py --codes 9984,2533,2121
"""

import argparse
import time
import random
import pathlib
import pandas as pd
from io import StringIO
from fetch import fetch_html

OUT_DIR = pathlib.Path("raw_html")
OUT_DIR.mkdir(exist_ok=True)


def inspect(code: str):
    url = f"https://kabutan.jp/stock/?code={code}"
    print("=" * 60)
    print(f"[{code}] GET {url}")
    html = fetch_html(url)

    html_path = OUT_DIR / f"stock_detail_{code}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"saved raw html -> {html_path}")

    try:
        tables = pd.read_html(StringIO(html))
    except ValueError as e:
        print(f"[!] テーブルが見つかりませんでした: {e}")
        return

    print(f"[OK] {len(tables)} 個の<table>を検出")
    for i, df in enumerate(tables):
        print(f"--- table[{i}] shape={df.shape} ---")
        print("columns:", list(df.columns)[:10])
        print(df.head(2).to_string())
        print()


def main():
    parser = argparse.ArgumentParser(description="個別銘柄ページの表構造調査")
    parser.add_argument("--codes", type=str, required=True, help="カンマ区切りの銘柄コード")
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    for i, code in enumerate(codes):
        if i > 0:
            time.sleep(random.uniform(3, 6))
        inspect(code)


if __name__ == "__main__":
    main()
