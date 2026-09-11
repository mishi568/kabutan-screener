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

# 地合い判断に使う日経平均関連マクロ指標のテーブル一覧。
# いずれも(date, ...)形式で、直近1件をMAX(date)で取得する。
_MACRO_TABLES = {
    "nt": "nikkei225jp_nt_ratio",
    "fear": "nikkei225jp_fear_index",
    "arb": "nikkei225jp_arbitrage",
    "karauri_n225jp": "nikkei225jp_short_selling",
    "karauri_jpx": "jpx_short_selling",
    "sinyou": "nikkei_margin_records",
    "futures": "nikkei225jp_futures_broker",
    "investor_jpx": "jpx_investor_trends",
    "per": "nikkei_per_records",
}


def _latest_row(conn, table: str) -> dict | None:
    row = conn.execute(f"SELECT * FROM {table} ORDER BY date DESC LIMIT 1").fetchone()
    if row is None:
        return None
    cols = [d[0] for d in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
    return dict(zip(cols, row))


def format_macro_overview(conn) -> str:
    """日経平均関連のマクロ・需給指標を要約し、AIへの相場観判断の指示を付けて返す。

    データが1つも無ければ空文字を返す(run_macro_sync.py未実行の場合、セクション自体を省略する)。
    """
    m = {key: _latest_row(conn, table) for key, table in _MACRO_TABLES.items()}
    if not any(m.values()):
        return ""

    lines = ["## 📊 【前提】全体相場環境(日経平均・需給マクロ指標)"]

    if m["per"]:
        r = m["per"]
        lines.append(f"- 日経平均: {r['price']:,.2f}円 / PER {r['per']}倍 / PBR {r['pbr']}倍 (基準日: {r['date']})")
    if m["nt"] and m["nt"]["nt_ratio"] is not None:
        r = m["nt"]
        lines.append(f"- NT倍率(日経平均/TOPIX): {r['nt_ratio']:.2f} (基準日: {r['date']}) ※上昇=値がさ株優位、下降=内需/中小型株優位の目安")
    if m["fear"] and m["fear"]["japan_vi"] is not None:
        r = m["fear"]
        lines.append(f"- 日本VI(恐怖指数): {r['japan_vi']:.2f} (基準日: {r['date']}) ※20未満は平静、30超は警戒、40超はパニック局面の目安")
    if m["sinyou"]:
        r = m["sinyou"]
        pl = f", 信用評価損益率 {r['profit_loss_ratio']:+.2f}%" if r["profit_loss_ratio"] is not None else ""
        lines.append(f"- 信用倍率(東証全体): {r['margin_ratio']}倍{pl} (基準日: {r['date']})")
    if m["karauri_jpx"] and m["karauri_jpx"]["short_selling_ratio"] is not None:
        r = m["karauri_jpx"]
        lines.append(f"- 空売り比率(JPX公式): {r['short_selling_ratio']:.2f}% (基準日: {r['date']})")
    elif m["karauri_n225jp"] and m["karauri_n225jp"]["short_ratio_total"] is not None:
        r = m["karauri_n225jp"]
        lines.append(f"- 空売り比率(nikkei225jp.com): {r['short_ratio_total']:.1f}% (基準日: {r['date']})")
    if m["arb"] and m["arb"]["net_shares"] is not None:
        r = m["arb"]
        lines.append(
            f"- 裁定買い残-売り残差引: {r['net_shares']:,.0f}千株 (基準日: {r['date']}) "
            f"※将来の機械的な現物売り圧力(裁定解消売り)の潜在量。高水準なほど上値が重い目安"
        )
    if m["futures"] and m["futures"]["foreign_net"] is not None:
        r = m["futures"]
        lines.append(f"- 日経225先物 外資系証券ネット建玉: {r['foreign_net']:+,.0f}枚 (基準週: {r['date']}) ※海外機関投資家の先物ポジション方向")
    if m["investor_jpx"]:
        r = m["investor_jpx"]
        parts = []
        if r["foreign_net"] is not None:
            parts.append(f"外国人 {r['foreign_net']:+,.0f}億円")
        if r["individual_net"] is not None:
            parts.append(f"個人 {r['individual_net']:+,.0f}億円")
        if r["trust_bank_net"] is not None:
            parts.append(f"信託銀行 {r['trust_bank_net']:+,.0f}億円")
        if parts:
            lines.append(f"- 投資部門別売買動向(JPX公式、基準日: {r['date']}): " + " / ".join(parts))

    lines.append("")
    lines.append(
        "**上記のマクロ・需給指標を踏まえて、まず現在の日本株市場全体の相場観"
        "(強気/中立/弱気とその理由)を判断してから、以下の個別銘柄の評価に進んでください。**"
    )
    return "\n".join(lines)


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

    macro_overview = format_macro_overview(conn)

    blocks = [format_stock_block(conn, code, date) for code in codes]
    parts = [header]
    if macro_overview:
        parts.append(macro_overview)
    parts.extend(blocks)
    content = "\n\n".join(parts)

    out_path = args.out or f"ai_brief_{date}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[OK] {out_path} を作成しました（{len(codes)}銘柄分）")
    print("このファイルの中身をAIチャットに貼り付けてください。")

    conn.close()


if __name__ == "__main__":
    main()
