# -*- coding: utf-8 -*-
"""
上位候補銘柄について、これまでに蓄積したデータ（シグナル・スコア・株価ヒストリー・
個別銘柄詳細）を1つのMarkdown文書にまとめる。これをAIチャットに貼り付けて、
改めて定性的なランキング・判断をしてもらうためのもの。
（アクセスなし、DBの集計だけ）

使い方:
  python compile_ai_brief.py --top 10
  python compile_ai_brief.py --codes 9984,2533,2121
"""

import argparse
import json
import datetime
from db import get_conn

SIGNAL_LABELS = {
    "tansaku_macd_buy": "MACD買いシグナル",
    "tansaku_parabolic_bull": "パラボリック陽転",
    "warning_above_ma25": "25日線上抜け",
    "warning_golden_cross": "ゴールデンクロス",
    "warning_margin_due_low": "信用安値期日到来(買い戻し圧力)",
}


def get_top_codes(conn, funnel_key: str, top: int):
    row = conn.execute(
        "SELECT MAX(pick_date) FROM screening_picks WHERE funnel_key = ?", (funnel_key,)
    ).fetchone()
    latest_date = row[0]
    if not latest_date:
        return [], None
    rows = conn.execute(
        "SELECT code FROM screening_picks WHERE funnel_key = ? AND pick_date = ? "
        "ORDER BY score DESC LIMIT ?",
        (funnel_key, latest_date, top),
    ).fetchall()
    return [r[0] for r in rows], latest_date


def get_hit_signals(conn, code: str, date: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT ranking_key FROM ranking_snapshots WHERE code = ? AND snapshot_date = ?",
        (code, date),
    ).fetchall()
    keys = [r[0] for r in rows if r[0] in SIGNAL_LABELS]
    return [SIGNAL_LABELS[k] for k in keys]


def get_recent_prices(conn, code: str, n: int = 10):
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM price_history WHERE code = ? ORDER BY date DESC LIMIT ?",
        (code, n),
    ).fetchall()
    return list(reversed(rows))


def get_latest_detail(conn, code: str):
    row = conn.execute(
        "SELECT data_json FROM stock_details WHERE code = ? ORDER BY snapshot_date DESC LIMIT 1",
        (code,),
    ).fetchone()
    return json.loads(row[0]) if row else None


def format_stock_block(conn, code: str, date: str) -> str:
    name_row = conn.execute("SELECT name, market FROM stocks WHERE code = ?", (code,)).fetchone()
    name, market = name_row if name_row else ("?", "?")

    lines = [f"## {code} {name}（{market}）"]

    signals = get_hit_signals(conn, code, date)
    if signals:
        lines.append(f"- 該当シグナル: {', '.join(signals)}")

    detail = get_latest_detail(conn, code)
    if detail:
        lines.append(f"- PER: {detail.get('per')} / PBR: {detail.get('pbr')} / "
                      f"利回り: {detail.get('yield')} / 信用倍率: {detail.get('margin_ratio')} / "
                      f"時価総額: {detail.get('market_cap')}")
        fin = detail.get("financials") or []
        if fin:
            lines.append("- 業績推移（決算期 / 売上高 / 経常益 / 最終益 / 1株益 / 1株配）:")
            for row in fin:
                lines.append(f"    {row.get('決算期')} / {row.get('売上高')} / {row.get('経常益')} / "
                              f"{row.get('最終益')} / {row.get('１株益')} / {row.get('１株配')}")
        mh = detail.get("margin_history") or []
        if mh:
            lines.append("- 信用残 週次推移（日付 / 売り残 / 買い残 / 倍率）:")
            for row in mh[:5]:
                lines.append(f"    {row.get('日付')} / {row.get('売り残')} / {row.get('買い残')} / {row.get('倍率')}")
    else:
        lines.append("- 個別詳細データなし（fetch_stock_detail.py未実行）")

    prices = get_recent_prices(conn, code, 10)
    if prices:
        lines.append("- 直近株価（日付 / 始値 / 高値 / 安値 / 終値 / 出来高）:")
        for d, o, h, l, c, v in prices:
            lines.append(f"    {d} / {o} / {h} / {l} / {c} / {v}")
    else:
        lines.append("- 株価ヒストリーなし（fetch_price_history.py未実行）")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="AIチャット向けダイジェスト生成")
    parser.add_argument("--top", type=int, default=None, help="score_ranking.pyの最新結果の上位N銘柄")
    parser.add_argument("--codes", type=str, default=None, help="カンマ区切りで銘柄コードを直接指定")
    parser.add_argument("--out", type=str, default=None, help="出力ファイル名（省略時は自動生成）")
    args = parser.parse_args()

    conn = get_conn()

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        date = datetime.date.today().isoformat()
    elif args.top:
        codes, date = get_top_codes(conn, "signal_score", args.top)
        if not codes:
            print("screening_picksにsignal_scoreの記録がありません。先にscore_ranking.pyを実行してください。")
            conn.close()
            return
    else:
        print("--codes か --top のどちらかを指定してください。")
        conn.close()
        return

    header = (
        f"# 株式スクリーニング ダイジェスト（対象日: {date}）\n\n"
        f"以下は株探から日次収集したデータに基づく候補銘柄 {len(codes)} 件です。"
        f"各銘柄の該当シグナル・PER/PBR/信用倍率・業績推移・信用残推移・直近株価を載せています。"
        f"これらの情報をもとに、改めて有望度のランキングと簡単な理由付けをしてください。\n"
    )

    blocks = [format_stock_block(conn, code, date) for code in codes]
    content = header + "\n\n" + "\n\n".join(blocks)

    out_path = args.out or f"ai_brief_{date}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] {out_path} を作成しました（{len(codes)}銘柄分）")
    print("このファイルの中身をAIチャットに貼り付けてください。")

    conn.close()


if __name__ == "__main__":
    main()
