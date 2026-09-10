# -*- coding: utf-8 -*-
"""
ファネル抽出スクリプト（アクセスなし、DBの集計だけ）。

Stage1: 信用需給系ランキング（7_1〜7_6のいずれか）に該当
Stage2: Stage1の中から、テクニカルのゴールデンクロス or 25日線上抜けにも該当

使い方：
  python funnel_screen.py --days 7
"""

import argparse
import datetime
from db import get_conn, insert_screening_picks

FUNNEL_KEY = "margin_x_technical_cross"  # このファネルの識別子（複数ファネルを併用するなら別の名前を）

STAGE1_RANKINGS = [
    "warning_margin_sell_up",
    "warning_margin_buy_up",
    "warning_margin_sell_down",
    "warning_margin_buy_down",
    "warning_margin_due_high",
    "warning_margin_due_low",
]

STAGE2_RANKINGS = [
    "warning_golden_cross",
    "warning_above_ma25",
]


def codes_in(conn, ranking_keys, days) -> set:
    placeholders = ",".join("?" for _ in ranking_keys)
    rows = conn.execute(
        f"""
        SELECT DISTINCT code
        FROM ranking_snapshots
        WHERE ranking_key IN ({placeholders})
          AND snapshot_date >= date('now', ?)
        """,
        (*ranking_keys, f"-{days} days"),
    ).fetchall()
    return {r[0] for r in rows}


def main():
    parser = argparse.ArgumentParser(description="信用需給×テクニカルクロスのファネル抽出")
    parser.add_argument("--days", type=int, default=7, help="直近何日分を対象にするか")
    args = parser.parse_args()

    conn = get_conn()
    stage1 = codes_in(conn, STAGE1_RANKINGS, args.days)
    stage2 = codes_in(conn, STAGE2_RANKINGS, args.days)
    final = stage1 & stage2

    print(f"Stage1（信用需給系 {len(STAGE1_RANKINGS)}種のいずれか）: {len(stage1)}銘柄")
    print(f"Stage2（ゴールデンクロス or 25日線上抜け）: {len(stage2)}銘柄")
    print(f"Stage1 ∩ Stage2: {len(final)}銘柄\n")

    if not final:
        print("該当なし。--days を広げるか、データを数日分溜めてから再度お試しください。")
        conn.close()
        return

    placeholders = ",".join("?" for _ in final)
    rows = conn.execute(
        f"SELECT code, name, market, last_seen FROM stocks WHERE code IN ({placeholders}) ORDER BY code",
        tuple(final),
    ).fetchall()
    for code, name, market, last_seen in rows:
        print(f"  {code:<8}{name:<14}{market:<6}最終出現:{last_seen}")

    today = datetime.date.today().isoformat()
    insert_screening_picks(conn, today, FUNNEL_KEY, sorted(final))
    print(f"\n[記録] screening_picks に保存しました（pick_date={today}, funnel_key={FUNNEL_KEY}）")

    conn.close()

    print("\n↓ここから個別チェック（kabuka）に進む例:")
    print(f"python fetch_price_history.py --codes {','.join(sorted(final))} --pages 9")


if __name__ == "__main__":
    main()
