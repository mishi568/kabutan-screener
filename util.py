# -*- coding: utf-8 -*-
"""
複数スクリプトで使い回す小さな共通ユーティリティ。
"""

# ETF/ETN/REIT/インフラファンドなど、個別株ではない市場区分（末尾記号で判定）
# 例: 東Ｅ=ETF, 東EN=ETN, 東IF=インフラファンド, 東R=REIT
FUND_MARKET_SUFFIXES = ("Ｅ", "EN", "IF", "R")


def is_fund_market(market: str) -> bool:
    if not market:
        return False
    return any(market.endswith(suf) for suf in FUND_MARKET_SUFFIXES)


def pct_to_float(s):
    """'+20.81%' や '8,461.21' のような文字列をfloatに変換する。失敗したらNone。"""
    if s is None:
        return None
    s = str(s).replace(",", "").replace("%", "").replace("+", "").strip()
    if s in ("－", "-", "—", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def get_top_codes_from_picks(conn, funnel_key: str, top: int) -> list[str]:
    """screening_picksの最新pick_dateについて、指定funnel_keyのスコア上位N銘柄コードを返す。"""
    row = conn.execute(
        "SELECT MAX(pick_date) FROM screening_picks WHERE funnel_key = ?", (funnel_key,)
    ).fetchone()
    latest_date = row[0]
    if not latest_date:
        return []
    rows = conn.execute(
        "SELECT code FROM screening_picks WHERE funnel_key = ? AND pick_date = ? "
        "ORDER BY score DESC LIMIT ?",
        (funnel_key, latest_date, top),
    ).fetchall()
    return [r[0] for r in rows]
