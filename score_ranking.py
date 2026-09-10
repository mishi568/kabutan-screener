# -*- coding: utf-8 -*-
"""
複数の強気シグナルへの該当数をスコア化して「おすすめランキング」を作るスクリプト。
（アクセスなし、DBの集計だけ）

デフォルトの重み付け（+1/-1というシンプルな加点方式。まずはここから、
実際のバックテスト結果を見ながら重みを調整していくのが良いと思います）：

  tansaku_macd_buy       : +1  MACD買いシグナル
  tansaku_parabolic_bull : +1  パラボリック陽転
  warning_above_ma25     : +1  25日移動平均線を上抜け
  warning_golden_cross   : +1  ゴールデンクロス（5日/25日）
  warning_margin_due_low : +1  信用【安値】期日到来（空売りの買い戻し圧力＝強気材料）

※ 信用【高値】期日到来（warning_margin_due_high）はスコアに含めない。
   「強制売りが出た直後は弱気、数週間後にあく抜け反発するかもしれない」という
   時間差のある指標なので、即時スコアには不向き。flag_watch_list.py で
   別枠のウォッチリストとして記録し、後日 price_history と突き合わせて検証する。

※ 信用買い残/売り残の増減（7_1〜7_4）はどちらとも解釈できる（将来の需給要因が
   複雑）ため、デフォルトではスコアに含めていません。加えたい場合はSIGNAL_WEIGHTSに
   追記してください。

使い方:
  python score_ranking.py --days 1 --top 20
"""

import argparse
import json
import datetime
from db import get_conn, insert_screening_picks
from util import is_fund_market, pct_to_float

SIGNAL_WEIGHTS = {
    "tansaku_macd_buy": 1,
    "tansaku_parabolic_bull": 1,
    "warning_above_ma25": 1,
    "warning_golden_cross": 1,
    "warning_margin_due_low": 1,
}

# 信用【高値】期日到来銘柄（warning_margin_due_high）はスコアに含めない。
# 「強制売りが出きった後、数週間後にあく抜け反発するか」を検証したい指標なので、
# 即時スコアではなく flag_watch_list.py で別枠のウォッチリストとして記録する。

# 急騰銘柄の除外設定：
#   ストップ高は無条件で除外（値幅制限いっぱいまで買われており、翌日以降の値動きが読みにくい）。
#   値上がり率ランキングは、当日の前日比%がSURGE_PCT_THRESHOLDを超えていたら除外
#   （シグナルが出ていても、その日のうちに既に大きく買われていると高値づかみのリスクが高い）。
SURGE_EXCLUDE_RANKINGS = ["warning_stop_high"]
SURGE_CHECK_RANKING = "warning_price_up"
SURGE_PCT_THRESHOLD = 15.0  # この%を超えて既に上昇していたら除外

FUNNEL_KEY = "signal_score"


def load_surge_codes(conn, target_date: str, threshold: float) -> dict:
    """当日すでに急騰している銘柄コード -> 理由文字列 の辞書を返す。"""
    surged = {}

    for ranking_key in SURGE_EXCLUDE_RANKINGS:
        rows = conn.execute(
            "SELECT DISTINCT code FROM ranking_snapshots WHERE ranking_key = ? AND snapshot_date = ?",
            (ranking_key, target_date),
        ).fetchall()
        for (code,) in rows:
            surged[code] = f"{ranking_key}"

    rows = conn.execute(
        "SELECT code, extra FROM ranking_snapshots WHERE ranking_key = ? AND snapshot_date = ?",
        (SURGE_CHECK_RANKING, target_date),
    ).fetchall()
    for code, extra in rows:
        if code in surged:
            continue
        d = json.loads(extra) if extra else {}
        pct = pct_to_float(d.get("前日比.1", d.get("前日比")))
        if pct is not None and pct >= threshold:
            surged[code] = f"前日比+{pct:.1f}%"

    return surged


def main():
    parser = argparse.ArgumentParser(description="シグナル加点方式のおすすめランキング")
    parser.add_argument("--days", type=int, default=1, help="直近何日分を対象にするか（デフォルト1=今日のみ）")
    parser.add_argument("--top", type=int, default=20, help="上位何件まで表示するか")
    parser.add_argument("--min-score", type=float, default=1.0, help="この点数未満は除外")
    parser.add_argument("--include-funds", action="store_true",
                         help="ETF/ETN/REITなどファンド系銘柄も対象に含める（デフォルトは除外）")
    parser.add_argument("--include-surged", action="store_true",
                         help="ストップ高・急騰銘柄も対象に含める（デフォルトは除外）")
    parser.add_argument("--surge-threshold", type=float, default=SURGE_PCT_THRESHOLD,
                         help=f"この前日比%%を超えていたら急騰扱いで除外（デフォルト{SURGE_PCT_THRESHOLD}）")
    args = parser.parse_args()

    today = datetime.date.today().isoformat()
    conn = get_conn()
    placeholders = ",".join("?" for _ in SIGNAL_WEIGHTS)
    rows = conn.execute(
        f"""
        SELECT code, ranking_key
        FROM ranking_snapshots
        WHERE ranking_key IN ({placeholders})
          AND snapshot_date >= date('now', ?)
        """,
        (*SIGNAL_WEIGHTS.keys(), f"-{args.days - 1} days"),
    ).fetchall()

    scores: dict[str, float] = {}
    hit_signals: dict[str, list[str]] = {}
    for code, ranking_key in rows:
        w = SIGNAL_WEIGHTS[ranking_key]
        scores[code] = scores.get(code, 0) + w
        hit_signals.setdefault(code, []).append(f"{ranking_key}({w:+d})")

    # top N を切り出す前に、全対象銘柄の市場区分を引いてファンド系を除外しておく
    # （先にtopで絞ってからだと、ファンドが枠を無駄に占有して個別株が漏れてしまう）
    all_codes = list(scores.keys())
    placeholders_all = ",".join("?" for _ in all_codes)
    market_map = {r[0]: r[1] for r in conn.execute(
        f"SELECT code, market FROM stocks WHERE code IN ({placeholders_all})", all_codes
    ).fetchall()} if all_codes else {}

    if not args.include_funds:
        excluded = [c for c in all_codes if is_fund_market(market_map.get(c, ""))]
        for c in excluded:
            del scores[c]
        if excluded:
            print(f"(ファンド系銘柄 {len(excluded)} 件を除外しました。含めたい場合は --include-funds)\n")

    if not args.include_surged:
        surge_codes = load_surge_codes(conn, today, args.surge_threshold)
        excluded_surge = [c for c in list(scores.keys()) if c in surge_codes]
        for c in excluded_surge:
            del scores[c]
        if excluded_surge:
            print(f"(急騰銘柄 {len(excluded_surge)} 件を除外しました。含めたい場合は --include-surged)")
            for c in excluded_surge:
                print(f"  {c}: {surge_codes[c]}")
            print()

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ranked = [(c, s) for c, s in ranked if s >= args.min_score][: args.top]

    if not ranked:
        print("該当なし（--min-score を下げるか、データを増やしてください）")
        conn.close()
        return

    codes = [c for c, _ in ranked]
    score_map = {c: s for c, s in ranked}
    placeholders2 = ",".join("?" for _ in codes)
    name_map = {r[0]: (r[1], r[2]) for r in conn.execute(
        f"SELECT code, name, market FROM stocks WHERE code IN ({placeholders2})", codes
    ).fetchall()}

    print(f"{'コード':<8}{'銘柄名':<14}{'市場':<6}{'スコア':<6}該当シグナル")
    for code, score in ranked:
        name, market = name_map.get(code, ("?", "?"))
        print(f"{code:<8}{name:<14}{market:<6}{score:<6}{', '.join(hit_signals[code])}")

    insert_screening_picks(conn, today, FUNNEL_KEY, codes, scores=score_map)
    print(f"\n[記録] screening_picks に保存しました（pick_date={today}, funnel_key={FUNNEL_KEY}）")

    conn.close()


if __name__ == "__main__":
    main()
