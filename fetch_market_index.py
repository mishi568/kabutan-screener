# -*- coding: utf-8 -*-
"""
地合い（市場全体）記録用：日経平均・グロース市場250指数などの日足を取得する。

kabutanでは指数も個別銘柄と全く同じ /stock/kabuka?code=XXXX ページ構成で日足が取れるため、
fetch_price_history.py の fetch_one_code() をそのまま再利用する（price_historyテーブルに
指数コード（0000, 0012など）をそのまま銘柄コードと同じ形で保存する。実在の銘柄コードと
衝突しない番号帯のため問題ない）。

この指数データは backtest.py で「シグナルが不発だったのは地合いが悪かったからか」を
判定するのに使う。

使い方:
  python fetch_market_index.py --pages 3
"""

import argparse
import random
import time
import datetime

from db import get_conn, upsert_stock
from fetch_price_history import fetch_one_code
from config import MARKET_INDICES


def main():
    parser = argparse.ArgumentParser(description="地合い（市場指数）の取得")
    parser.add_argument("--pages", type=int, default=2, help="取得ページ数（1ページ≒1ヶ月弱）")
    parser.add_argument("--sleep-min", type=float, default=3.0)
    parser.add_argument("--sleep-max", type=float, default=6.0)
    args = parser.parse_args()

    today = datetime.date.today().isoformat()
    conn = get_conn()

    for i, (code, name) in enumerate(MARKET_INDICES.items()):
        if i > 0:
            time.sleep(random.uniform(args.sleep_min, args.sleep_max))
        print(f"[{code}] {name}")
        upsert_stock(conn, code, name, "INDEX", today)
        n_new = fetch_one_code(conn, code, args.pages, args.sleep_min, args.sleep_max)
        print(f"  新規 {n_new} 件保存")

    conn.close()


if __name__ == "__main__":
    main()
