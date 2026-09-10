# -*- coding: utf-8 -*-
"""
データの健全性チェック（アクセスなし）。

1. 日付ごとに、config.RANKINGS に定義された全ランキングのうち
   実際にDBへ記録されているものはいくつか（＝取得が途中で止まった日を検出）
2. price_history の取得進捗（まだ終端に到達していない銘柄）の一覧

使い方:
  python check_data_health.py
"""

from config import RANKINGS
from db import get_conn


def main():
    conn = get_conn()
    expected_keys = set(RANKINGS.keys())

    print(f"config.py上のランキング定義数: {len(expected_keys)}\n")

    print("=== 日付ごとのランキング取得カバレッジ ===")
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT snapshot_date FROM ranking_snapshots ORDER BY snapshot_date"
    ).fetchall()]

    for date in dates:
        got_keys = {r[0] for r in conn.execute(
            "SELECT DISTINCT ranking_key FROM ranking_snapshots WHERE snapshot_date = ?", (date,)
        ).fetchall()}
        missing = expected_keys - got_keys
        # 過去に一度も追跡していなかったランキング（新規追加分など）は「未来のconfigにだけ存在」なので分けて表示
        status = "OK" if not missing else f"欠け {len(missing)}件"
        print(f"  {date}: {len(got_keys)}/{len(expected_keys)} 件  [{status}]")
        if missing:
            print(f"    -> 欠けているranking_key: {sorted(missing)}")

    print("\n=== price_historyの取得が終端に到達していない銘柄 ===")
    rows = conn.execute(
        "SELECT code, max_page_fetched, reached_end FROM price_history_progress WHERE reached_end = 0 ORDER BY code"
    ).fetchall()
    if not rows:
        print("  なし（全銘柄が終端に到達済み、またはまだ何も取得していません）")
    else:
        for code, max_page, reached_end in rows:
            print(f"  {code}: {max_page}ページ目まで取得済み（未完了）")

    conn.close()


if __name__ == "__main__":
    main()
