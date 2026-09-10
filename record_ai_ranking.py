# -*- coding: utf-8 -*-
"""
AIチャット（Claudeなど）が ai_brief_*.md を見て出した定性的ランキングを
screening_picksに記録するスクリプト（アクセスなし）。

funnel_key="ai_qualitative_rank" として保存する。数週間後にprice_historyと
突き合わせて、「AIのその日の順位付けは、その後の値動きとどれくらい合っていたか」
を検証できるようにするため。

使い方:
  python record_ai_ranking.py --ranking "1770:10,2121:9,2533:8,3856:7,1444:3,2923:3,3070:2,3773:3,3998:3,4441:3"
  python record_ai_ranking.py --ranking "..." --date 2026-09-10
"""

import argparse
import datetime
from db import get_conn, insert_screening_picks

FUNNEL_KEY = "ai_qualitative_rank"


def main():
    parser = argparse.ArgumentParser(description="AI定性ランキングの記録")
    parser.add_argument("--ranking", type=str, required=True,
                         help="'コード:スコア,コード:スコア,...' の形式。スコアが高いほど上位。")
    parser.add_argument("--date", type=str, default=None, help="対象日（省略時は今日）")
    args = parser.parse_args()

    target_date = args.date or datetime.date.today().isoformat()

    pairs = [p.strip() for p in args.ranking.split(",") if p.strip()]
    scores = {}
    for p in pairs:
        code, _, score_str = p.partition(":")
        scores[code.strip()] = float(score_str) if score_str else 0.0

    codes = list(scores.keys())
    conn = get_conn()
    insert_screening_picks(conn, target_date, FUNNEL_KEY, codes, scores=scores)
    conn.close()

    print(f"{target_date}: {len(codes)}銘柄を funnel_key={FUNNEL_KEY} として記録しました")
    for code, score in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {code}: score={score}")


if __name__ == "__main__":
    main()
