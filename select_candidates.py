# -*- coding: utf-8 -*-
"""
一次審査スクリプト。

これまでに蓄積した ranking_snapshots だけを使ってローカルで集計するので、
株探への追加アクセスは一切発生しません。

「直近N日間で、M種類以上のランキングに登場した銘柄」を候補として抽出します。
複数のシグナルが重なっている銘柄ほど注目度が高いはず、という考え方です。

この結果（コード一覧）を fetch_price_history.py の --codes に渡すことで、
株価ヒストリーを取得する対象を「全銘柄」ではなく「厳選した候補」に絞り込めます。
これにより株探へのアクセス回数を大幅に削減できます。

使い方：
  python select_candidates.py                     # デフォルト設定で表示
  python select_candidates.py --min-hits 3 --days 14 --top 20
"""

import argparse
from db import get_conn
from util import is_fund_market


def main():
    parser = argparse.ArgumentParser(description="一次審査：複数ランキング出現銘柄の抽出")
    parser.add_argument("--min-hits", type=int, default=2,
                         help="何種類以上のランキングに登場したら候補とするか（デフォルト2）")
    parser.add_argument("--days", type=int, default=7,
                         help="直近何日分のスナップショットを対象にするか（デフォルト7日）")
    parser.add_argument("--top", type=int, default=30,
                         help="上位何件まで表示するか（デフォルト30）")
    parser.add_argument("--include-funds", action="store_true",
                         help="ETF/ETN/REITなどファンド系銘柄も候補に含める（デフォルトは除外）")
    args = parser.parse_args()

    conn = get_conn()
    rows = conn.execute(
        """
        SELECT s.code, s.name, s.market,
               COUNT(DISTINCT r.ranking_key) AS ranking_hits,
               COUNT(DISTINCT r.snapshot_date) AS day_hits,
               GROUP_CONCAT(DISTINCT r.ranking_key) AS rankings
        FROM ranking_snapshots r
        JOIN stocks s ON s.code = r.code
        WHERE r.snapshot_date >= date('now', ?)
        GROUP BY s.code
        HAVING ranking_hits >= ?
        ORDER BY ranking_hits DESC, day_hits DESC
        """,
        (f"-{args.days} days", args.min_hits),
    ).fetchall()
    conn.close()

    if not args.include_funds:
        excluded = [r for r in rows if is_fund_market(r[2])]
        rows = [r for r in rows if not is_fund_market(r[2])]
        if excluded:
            print(f"(ファンド系銘柄 {len(excluded)} 件を除外しました。含めたい場合は --include-funds)")

    rows = rows[: args.top]

    if not rows:
        print("該当銘柄なし。--min-hits を下げるか、run_daily.py をもう数日回してデータを増やしてください。")
        return

    print(f"{'コード':<8}{'銘柄名':<14}{'市場':<6}{'ﾗﾝｷﾝｸﾞ数':<10}{'延べ日数':<8}登場ランキング")
    codes = []
    for code, name, market, hits, days, rankings in rows:
        codes.append(code)
        print(f"{code:<8}{name:<14}{market:<6}{hits:<10}{days:<8}{rankings}")

    print(f"\n候補銘柄数: {len(codes)}")
    print("↓このままfetch_price_historyに渡せます")
    print(f"python fetch_price_history.py --codes {','.join(codes)} --pages 9")


if __name__ == "__main__":
    main()
