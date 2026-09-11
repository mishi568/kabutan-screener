# -*- coding: utf-8 -*-
"""
個別銘柄の詳細ページ（PER/PBR/信用倍率/業績推移/信用取引週次など）を取得し、
stock_details テーブルに保存するスクリプト。

使い方:
  python fetch_stock_detail.py --codes 9984,2533,2121
  python fetch_stock_detail.py --top 10   # score_ranking.pyの最新結果(funnel_key=signal_score)の上位N銘柄
"""

import argparse
import time
import random
import json
import datetime

from fetch import fetch_html
from parse import parse_stock_detail
from db import get_conn, insert_stock_detail
from util import get_top_codes_from_picks


def has_detail_today(conn, code: str, today: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM stock_details WHERE code = ? AND snapshot_date = ?", (code, today)
    ).fetchone()
    return row is not None


BASE_URL = "https://kabutan.jp/stock/?code={code}"


def main():
    parser = argparse.ArgumentParser(description="個別銘柄詳細ページの取得")
    parser.add_argument("--codes", type=str, default=None, help="カンマ区切りで銘柄コードを直接指定")
    parser.add_argument("--top", type=int, default=None,
                         help="score_ranking.py(funnel_key=signal_score)の最新結果の上位N銘柄を対象にする")
    parser.add_argument("--sleep-min", type=float, default=3.0)
    parser.add_argument("--sleep-max", type=float, default=6.0)
    parser.add_argument("--force", action="store_true", help="本日すでに取得済みの銘柄も強制的に再取得する")
    args = parser.parse_args()

    conn = get_conn()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    elif args.top:
        codes = get_top_codes_from_picks(conn, "signal_score", args.top)
        if not codes:
            print("screening_picksにsignal_scoreの記録がありません。先にscore_ranking.pyを実行してください。")
            conn.close()
            return
    else:
        print("--codes か --top のどちらかを指定してください。")
        conn.close()
        return

    today = datetime.date.today().isoformat()
    print(f"対象銘柄: {codes}")

    fetched_any = False
    for i, code in enumerate(codes):
        if not args.force and has_detail_today(conn, code, today):
            print(f"[{i+1}/{len(codes)}] {code}  本日は取得済みのためスキップします（--forceで強制再取得できます）")
            continue

        if fetched_any:
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))
        fetched_any = True

        url = BASE_URL.format(code=code)
        print(f"[{i+1}/{len(codes)}] {code} -> {url}")
        try:
            html = fetch_html(url)
            detail = parse_stock_detail(html)
        except Exception as e:
            print(f"  [NG] {e}")
            continue

        insert_stock_detail(conn, code, today, json.dumps(detail, ensure_ascii=False))
        print(f"  [OK] PER={detail.get('per')} PBR={detail.get('pbr')} "
              f"信用倍率={detail.get('margin_ratio')} 業績件数={len(detail.get('financials', []))}")

    conn.close()


if __name__ == "__main__":
    main()
