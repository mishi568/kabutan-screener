# -*- coding: utf-8 -*-
"""
バックテスト用：個別銘柄の日足四本値ヒストリーを取得するスクリプト。

日次のrun_daily.pyとは別の、時々まとめて回す「バックフィル」用スクリプトです。
対象は基本的に stocks テーブル（＝これまでにランキングへ出現した銘柄）ですが、
--codes で個別指定も可能です。

差分更新の仕組み（修正版）：
  銘柄ごとに「何ページ目まで取得済みか」を price_history_progress テーブルに記録します。
  次回実行時は、その続きのページ番号から取得を再開します
  （以前は「ページの中身が既知データだけなら打ち切り」という判定でしたが、
   浅い --pages で一度止めた後に深い --pages で再実行すると、
   本来取得すべき深いページまで届かずに打ち切られてしまうバグがあったため、
   ページ番号ベースの進捗管理に変更しました）。
  データが尽きた（表が空になった）ページに到達したら reached_end=1 を記録し、
  以降はその銘柄をスキップします。

使い方の例：
  # まず5銘柄だけ、3ページ（直近2ヶ月程度）試す
  python fetch_price_history.py --limit 5 --pages 3

  # 問題なければ全銘柄・深めに遡る（初回バックフィル。時間がかかります）
  python fetch_price_history.py --pages 9

  # 日々の差分更新だけしたい場合（run_daily.pyの後に回す想定）
  python fetch_price_history.py --pages 2
"""

import argparse
import random
import time

from fetch import fetch_html
from parse import find_price_history_table, price_history_to_records
from db import get_conn, get_all_codes, get_known_dates, insert_price_history, get_progress, set_progress

BASE_URL = "https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page={page}"


def fetch_one_code(conn, code: str, max_pages: int, sleep_min: float, sleep_max: float):
    known_dates = get_known_dates(conn, code)
    prev_max_page, reached_end = get_progress(conn, code)

    if reached_end and prev_max_page >= max_pages:
        print(f"  取得済み（{prev_max_page}ページ目で履歴の終端まで到達済み）。スキップ")
        return 0

    start_page = prev_max_page + 1
    total_new = 0
    last_page_done = prev_max_page

    for page in range(start_page, max_pages + 1):
        if page > start_page:
            time.sleep(random.uniform(sleep_min, sleep_max))

        url = BASE_URL.format(code=code, page=page)
        try:
            html = fetch_html(url)
            df = find_price_history_table(html)
        except Exception as e:
            print(f"  [NG] page{page}: {e}")
            break

        if df is None or df.empty:
            print(f"  page{page}: データなし（履歴の終端に到達）")
            set_progress(conn, code, last_page_done, reached_end=True)
            conn.commit()
            return total_new

        records = price_history_to_records(df, code)
        new_records = [r for r in records if r["date"] not in known_dates]

        insert_price_history(conn, records)
        last_page_done = page
        total_new += len(new_records)
        print(f"  page{page}: {len(records)}件中 新規{len(new_records)}件")

    set_progress(conn, code, last_page_done, reached_end=False)
    conn.commit()
    return total_new


def main():
    parser = argparse.ArgumentParser(description="株価ヒストリーのバックフィル取得")
    parser.add_argument("--pages", type=int, default=3, help="銘柄ごとの最大取得ページ数（1ページ≒1ヶ月弱）")
    parser.add_argument("--limit", type=int, default=None, help="対象銘柄数の上限（テスト用）")
    parser.add_argument("--codes", type=str, default=None, help="カンマ区切りで銘柄コードを直接指定")
    parser.add_argument("--sleep-min", type=float, default=3.0)
    parser.add_argument("--sleep-max", type=float, default=6.0)
    args = parser.parse_args()

    conn = get_conn()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = get_all_codes(conn)
        if args.limit:
            codes = codes[: args.limit]

    print(f"対象銘柄数: {len(codes)} / 銘柄あたり最大{args.pages}ページ")

    total = 0
    for i, code in enumerate(codes):
        if i > 0:
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))
        print(f"[{i+1}/{len(codes)}] code={code}")
        total += fetch_one_code(conn, code, args.pages, args.sleep_min, args.sleep_max)

    conn.close()
    print(f"\n完了: 新規保存 {total} 件")


if __name__ == "__main__":
    main()
