# -*- coding: utf-8 -*-
"""
保有銘柄（ポートフォリオ）の登録・解除を行うスクリプト（アクセスなし）。

screening_picks（スクリーニング候補）とは別枠の holdings テーブルで管理する。
実際の株価・参考情報の取得は fetch_holdings_price.py で行う。

使い方:
  python manage_holdings.py add 2121,2533 --memo "初期ポジション"
  python manage_holdings.py remove 2121
  python manage_holdings.py list
"""

import argparse
import datetime

from db import get_conn, add_holding, remove_holding, get_all_holdings


def main():
    parser = argparse.ArgumentParser(description="保有銘柄の管理")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="保有銘柄を追加（既存なら保有中に戻す）")
    p_add.add_argument("codes", type=str, help="カンマ区切りで銘柄コードを指定")
    p_add.add_argument("--memo", type=str, default=None)
    p_add.add_argument("--date", type=str, default=None, help="登録日（省略時は今日）")

    p_remove = sub.add_parser("remove", help="保有銘柄を解除（売却済みにする。履歴は残る）")
    p_remove.add_argument("codes", type=str, help="カンマ区切りで銘柄コードを指定")
    p_remove.add_argument("--date", type=str, default=None, help="解除日（省略時は今日）")

    sub.add_parser("list", help="登録済み保有銘柄の一覧（保有中・解除済み含む）")

    args = parser.parse_args()
    conn = get_conn()
    today = datetime.date.today().isoformat()

    if args.command == "add":
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        for code in codes:
            add_holding(conn, code, added_date=args.date or today, memo=args.memo)
        print(f"追加（保有中に設定）: {codes}")

    elif args.command == "remove":
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        for code in codes:
            remove_holding(conn, code, removed_date=args.date or today)
        print(f"解除: {codes}")

    elif args.command == "list":
        rows = get_all_holdings(conn)
        if not rows:
            print("登録済みの保有銘柄はありません。")
        else:
            print(f"{'コード':<8}{'銘柄名':<14}{'登録日':<12}{'解除日':<12}メモ")
            for code, name, memo, added, removed in rows:
                status = removed or "-"
                print(f"{code:<8}{(name or '?'):<14}{added:<12}{status:<12}{memo or ''}")

    conn.close()


if __name__ == "__main__":
    main()
