# -*- coding: utf-8 -*-
"""
「今すぐのシグナル」ではなく「時間差で効いてくるかもしれないシグナル」を
screening_picksに別枠（専用のfunnel_key）で記録しておくスクリプト。
（アクセスなし、DBの集計だけ）

対象: warning_margin_due_high（信用【高値】期日到来銘柄）
  強制決済売りが出た直後は弱気材料だが、「出きった後」は需給が軽くなって
  あく抜け反発する、という説がある。この仮説を後日 price_history と
  突き合わせて検証できるように、載った日付ごとに記録しておく。

run_daily.py の後に、毎日これも回しておくのがおすすめです。

使い方:
  python flag_watch_list.py
  python flag_watch_list.py --date 2026-09-10   # 過去日を手動指定したい場合
"""

import argparse
import datetime
from db import get_conn, insert_screening_picks

WATCH_KEY = "margin_due_high_watch"
SOURCE_RANKING = "warning_margin_due_high"


def main():
    parser = argparse.ArgumentParser(description="時間差シグナルのウォッチリスト記録")
    parser.add_argument("--date", type=str, default=None, help="対象日（省略時は今日）")
    args = parser.parse_args()

    target_date = args.date or datetime.date.today().isoformat()
    conn = get_conn()

    rows = conn.execute(
        "SELECT DISTINCT code FROM ranking_snapshots WHERE ranking_key = ? AND snapshot_date = ?",
        (SOURCE_RANKING, target_date),
    ).fetchall()
    codes = [r[0] for r in rows]

    if not codes:
        print(f"{target_date}: {SOURCE_RANKING} に該当銘柄なし（run_daily.pyを先に実行済みか確認してください）")
        conn.close()
        return

    insert_screening_picks(conn, target_date, WATCH_KEY, codes)
    print(f"{target_date}: {len(codes)}銘柄を funnel_key={WATCH_KEY} として記録しました")
    print(f"  {codes}")
    print("\n数週間後、これらの銘柄のprice_historyを見て「あく抜け反発」したか検証できます。")

    conn.close()


if __name__ == "__main__":
    main()
