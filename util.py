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
    """'+20.81%' のような文字列を 20.81 のようなfloatに変換する。失敗したらNone。"""
    if s is None:
        return None
    s = str(s).replace("%", "").replace("+", "").strip()
    try:
        return float(s)
    except ValueError:
        return None
