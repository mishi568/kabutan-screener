# -*- coding: utf-8 -*-
"""
保有銘柄専用の価格データベースを更新するスクリプト。

manage_holdings.py で登録した保有銘柄について、
  1. 株価（日足四本値）を holdings_price_history に保存
  2. 参考情報（PER/PBR/利回り/信用倍率/時価総額/業績推移/信用残週次）を
     stock_details に保存（fetch_stock_detail.py と同じテーブル・同じ形式）
をまとめて取得する。

fetch_price_history.py（price_history用）は「深いページへのバックフィル」専用の
進捗管理で、一度取得したページより浅いページ（＝最新の日足）を二度と取り直さない
設計になっている。保有銘柄は常に最新の値動きを追いたいので、進捗管理は使わず、
毎回シンプルに直近ページ（デフォルト1ページ≒1ヶ月弱）を取り直す方式にしている
（既存の日付はINSERT OR IGNOREで自動的に重複排除される）。

使い方:
  python fetch_holdings_price.py                    # 保有銘柄全件、直近1ページを更新
  python fetch_holdings_price.py --pages 9           # 新規追加銘柄などで深く遡りたいとき
  python fetch_holdings_price.py --codes 2121,2533 --pages 9
"""

import argparse
import json
import random
import time
import datetime

from fetch import fetch_html
from parse import find_price_history_table, price_history_to_records, parse_stock_detail, extract_stock_name
from db import get_conn, get_active_holdings, insert_holdings_price, insert_stock_detail, upsert_stock

PRICE_URL = "https://kabutan.jp/stock/kabuka?code={code}&ashi=day&page={page}"
DETAIL_URL = "https://kabutan.jp/stock/?code={code}"


def fetch_price(conn, code: str, pages: int, sleep_min: float, sleep_max: float) -> int:
    total = 0
    for page in range(1, pages + 1):
        if page > 1:
            time.sleep(random.uniform(sleep_min, sleep_max))
        html = fetch_html(PRICE_URL.format(code=code, page=page))
        df = find_price_history_table(html)
        if df is None or df.empty:
            break
        records = price_history_to_records(df, code)
        insert_holdings_price(conn, records)
        total += len(records)
    return total


def fetch_detail(conn, code: str, today: str):
    html = fetch_html(DETAIL_URL.format(code=code))
    name = extract_stock_name(html)
    detail = parse_stock_detail(html)
    if name:
        upsert_stock(conn, code, name, "-", today)
    insert_stock_detail(conn, code, today, json.dumps(detail, ensure_ascii=False))
    return name, detail


def main():
    parser = argparse.ArgumentParser(description="保有銘柄の株価・参考情報の取得")
    parser.add_argument("--codes", type=str, default=None,
                         help="カンマ区切りで銘柄コードを直接指定（省略時はholdingsの保有中銘柄全件）")
    parser.add_argument("--pages", type=int, default=1,
                         help="株価の取得ページ数（1ページ≒1ヶ月弱、デフォルト1=直近月のみ更新）")
    parser.add_argument("--sleep-min", type=float, default=3.0)
    parser.add_argument("--sleep-max", type=float, default=6.0)
    args = parser.parse_args()

    conn = get_conn()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = get_active_holdings(conn)

    if not codes:
        print("保有銘柄が登録されていません。先に manage_holdings.py add で登録してください。")
        conn.close()
        return

    today = datetime.date.today().isoformat()
    print(f"対象銘柄: {codes}")

    for i, code in enumerate(codes):
        if i > 0:
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))
        print(f"[{i+1}/{len(codes)}] {code}")

        try:
            n_new = fetch_price(conn, code, args.pages, args.sleep_min, args.sleep_max)
            conn.commit()
            print(f"  [OK] 株価 {n_new} 件保存")
        except Exception as e:
            print(f"  [NG] 株価取得失敗: {e}")
            continue

        time.sleep(random.uniform(args.sleep_min, args.sleep_max))

        try:
            name, detail = fetch_detail(conn, code, today)
            conn.commit()
            print(f"  [OK] 参考情報: 銘柄名={name} PER={detail.get('per')} PBR={detail.get('pbr')} "
                  f"信用倍率={detail.get('margin_ratio')} 業績件数={len(detail.get('financials', []))}")
        except Exception as e:
            print(f"  [NG] 参考情報取得失敗: {e}")

    conn.close()


if __name__ == "__main__":
    main()
