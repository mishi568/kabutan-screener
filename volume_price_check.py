# -*- coding: utf-8 -*-
"""
出来高と値動きの「矛盾」を検出するスクリプト（アクセスなし、DBの集計だけ）。

Type A: 出来高ランキング上位なのに、値動きがほぼゼロ（綱引き・様子見の可能性）
         ※ただし低位株（株価が数十円）は同じ売買代金でも株数が莫大になるため、
           出来高ランキング上位に構造的に入りやすい点は割り引いて見てください。

Type B: 値動き系ランキング（値上がり率・値下がり率・ストップ高・ストップ安）に
         載っているのに、出来高ランキング／出来高急増銘柄のどちらにも
         出てこない銘柄（＝値動きの出来高的な裏付けが薄い）

使い方：
  python volume_price_check.py
  python volume_price_check.py --date 2026-09-10 --flat-threshold 1.0
"""

import json
import argparse
import datetime
from db import get_conn
from util import pct_to_float


def load_snapshot(conn, ranking_key: str, date: str) -> dict:
    rows = conn.execute(
        "SELECT code, name, market, extra FROM ranking_snapshots WHERE ranking_key = ? AND snapshot_date = ?",
        (ranking_key, date),
    ).fetchall()
    result = {}
    for code, name, market, extra in rows:
        d = json.loads(extra) if extra else {}
        d["name"] = name
        d["market"] = market
        result[code] = d
    return result


def main():
    parser = argparse.ArgumentParser(description="出来高と値動きの矛盾チェック")
    parser.add_argument("--date", type=str, default=None, help="対象日（省略時は今日）")
    parser.add_argument("--flat-threshold", type=float, default=1.0,
                         help="Type Aで「値動きが小さい」とみなす前日比%の閾値（デフォルト1.0）")
    args = parser.parse_args()

    target_date = args.date or datetime.date.today().isoformat()
    conn = get_conn()

    volume_ranking = load_snapshot(conn, "warning_volume_ranking", target_date)
    volume_up = load_snapshot(conn, "tansaku_volume_up", target_date)

    print(f"対象日: {target_date}\n")

    # --- Type A ---
    print(f"=== Type A: 出来高上位なのに値動きが小さい（|前日比%| < {args.flat_threshold}） ===")
    hits_a = 0
    for code, d in volume_ranking.items():
        pct = pct_to_float(d.get("前日比.1"))
        vol = d.get("出来高")
        if pct is not None and abs(pct) < args.flat_threshold:
            hits_a += 1
            print(f"  {code:<7}{d['name']:<12}株価={d.get('株価'):>10}  出来高={vol:>14,.0f}  前日比={d.get('前日比.1')}")
    if hits_a == 0:
        print("  該当なし")

    # --- Type B ---
    # 元の設計（出来高ランキングTOP15とのクロス参照）は、TOP15という母集団が
    # 狭すぎてほぼ全銘柄がヒットしてしまい機能しなかったため、
    # 「値動き系ランキング自体が持つ出来高列」を使い、そのランキング内で
    # 相対的に出来高が薄い銘柄（下位25%）を検出する方式に変更。
    print(f"\n=== Type B: 値動きが大きいのに、同じランキング内で出来高が相対的に薄い銘柄 ===")
    hits_b = 0
    for ranking_key, label in [
        ("warning_price_up", "値上がり率"),
        ("warning_price_down", "値下がり率"),
        ("warning_stop_high", "ストップ高"),
        ("warning_stop_low", "ストップ安"),
    ]:
        movers = load_snapshot(conn, ranking_key, target_date)
        vols = [d.get("出来高") for d in movers.values() if isinstance(d.get("出来高"), (int, float))]
        if len(vols) < 4:
            continue  # 母数が少なすぎるパーセンタイル判定はスキップ
        vols_sorted = sorted(vols)
        threshold = vols_sorted[len(vols_sorted) // 4]  # 下位25%ライン

        for code, d in movers.items():
            vol = d.get("出来高")
            if isinstance(vol, (int, float)) and vol <= threshold:
                hits_b += 1
                pct_display = d.get("前日比.1", d.get("前日比"))
                print(f"  [{label:<6}] {code:<7}{d['name']:<12}前日比={pct_display:<10}出来高={vol:>12,.0f}")
    if hits_b == 0:
        print("  該当なし")

    conn.close()


if __name__ == "__main__":
    main()
