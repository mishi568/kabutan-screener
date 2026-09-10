# -*- coding: utf-8 -*-
"""
kabutan.jp のスクレイピング処理。

方針: kabutanのHTML構造（class名など）は将来変わりうるため、できるだけ
「見出しセルのテキスト」を手がかりにテーブルと列位置を探す、位置に強い
実装にしている（共通ロジックは html_utils.py）。もし kabutan 側のページ
構成が大きく変わった場合は、ScraperError が分かりやすいメッセージ付きで
送出されるので、data/raw_pages/ に保存された生HTMLを見ながら本ファイルの
*_HEADER_ALIASES を調整してほしい。

取得はPlaywright（ヘッドレスChromium）経由で行う。requestsによる単純な
HTTPアクセスでは、kabutan.jp側のbot対策とみられる挙動によりテーブルの
中身が空になる症状が確認されたため、実ブラウザでページを描画させてから
HTMLを取得する方式にしている（browser_fetch.py）。
"""

import time
from datetime import datetime

from bs4 import BeautifulSoup

from . import config
from .html_utils import (
    ScraperError,
    norm_text,
    parse_number,
    find_table_by_headers,
    column_index_map,
)

__all__ = [
    "ScraperError",
    "parse_number",
    "fetch_fundamental_candidates",
    "fetch_technical_candidates",
    "fetch_credit_data",
    "now_jst_string",
]


RANKING_HEADER_ALIASES = {
    "code": ["コード"],
    "name": ["銘柄名", "銘柄"],
    "market": ["市場"],
    "price": ["株価", "現在値"],
}

FUNDAMENTAL_EXTRA_ALIASES = {
    "streak": ["連続増益", "連続"],
    "prev_growth": ["前期", "実績増益率", "前期実績"],
    "this_growth": ["今期予想増益率", "今期予想", "予想増益率"],
    "avg_growth": ["平均増益率", "期間平均"],
    "per": ["ＰＥＲ", "PER"],
}

TECHNICAL_EXTRA_ALIASES = {
    "dev25": ["25日線", "25日"],
    "dev75": ["75日線", "75日"],
    "dev200": ["200日線", "200日"],
    "per": ["ＰＥＲ", "PER"],
    "pbr": ["ＰＢＲ", "PBR"],
    "yield": ["利回り"],
}

CREDIT_HEADER_ALIASES = {
    "date": ["日付", "申込日"],
    "sell": ["売り残"],
    "buy": ["買い残"],
    "ratio": ["倍率"],
}


def _is_target_market(market_text):
    return any(m in market_text for m in config.TARGET_MARKETS)


def _fetch_ranking_pages(fetcher, base_url, extra_alias_map, kind_label):
    """ページング付きランキング一覧を全ページ取得し、辞書のリストで返す。"""
    all_rows = []
    seen_codes_first_page = None
    for page in range(1, config.MAX_RANKING_PAGES + 1):
        sep = "&" if "?" in base_url else "?"
        url = base_url if page == 1 else "{}{}page={}".format(base_url, sep, page)
        html = fetcher.get(url, debug_name="{}_page{}.html".format(kind_label, page))
        soup = BeautifulSoup(html, "lxml")

        required_groups = [
            RANKING_HEADER_ALIASES["code"],
            RANKING_HEADER_ALIASES["name"],
            RANKING_HEADER_ALIASES["market"],
        ]
        table, header_texts = find_table_by_headers(soup, required_groups)
        if table is None:
            if page == 1:
                raise ScraperError(
                    "{}: ランキング表が見つかりませんでした。kabutan.jpの"
                    "ページ構成が変わっている可能性があります。".format(kind_label)
                )
            break  # 2ページ目以降で見つからない＝最終ページを超えた

        alias_map = dict(RANKING_HEADER_ALIASES)
        alias_map.update(extra_alias_map)
        col = column_index_map(header_texts, alias_map)

        body = table.find("tbody") or table
        data_rows = [
            tr for tr in body.find_all("tr")
            if tr.find("td") is not None
        ]
        if not data_rows:
            break

        page_codes = []
        for tr in data_rows:
            cells = tr.find_all("td")
            if len(cells) <= max(col.values()):
                continue
            row = {}
            for logical_name, i in col.items():
                text = norm_text(cells[i].get_text())
                row[logical_name] = text
            page_codes.append(row.get("code"))
            all_rows.append(row)

        if page == 1:
            seen_codes_first_page = page_codes
        elif page_codes == seen_codes_first_page:
            # kabutanが末尾ページ超過時に1ページ目を再表示するケースへの保険
            all_rows = all_rows[: -len(page_codes)]
            break

        time.sleep(config.REQUEST_DELAY_SEC)

    return all_rows


def fetch_fundamental_candidates(fetcher):
    """通期『営業利益』連続増益ランキングを取得する。"""
    rows = _fetch_ranking_pages(
        fetcher, config.FUNDAMENTAL_RANKING_URL, FUNDAMENTAL_EXTRA_ALIASES, "fundamental"
    )
    out = []
    for r in rows:
        if not _is_target_market(r.get("market", "")):
            continue
        streak = parse_number(r.get("streak"))
        if streak is None or streak < config.MIN_PROFIT_GROWTH_STREAK:
            continue
        out.append({
            "code": r.get("code"),
            "name": r.get("name"),
            "market": r.get("market"),
            "price": parse_number(r.get("price")),
            "streak": int(streak),
            "prev_growth": parse_number(r.get("prev_growth")),
            "this_growth": parse_number(r.get("this_growth")),
            "avg_growth": parse_number(r.get("avg_growth")),
            "per": parse_number(r.get("per")),
        })
    return out


def fetch_technical_candidates(fetcher):
    """移動平均線上昇トレンド銘柄ランキングを取得する。"""
    rows = _fetch_ranking_pages(
        fetcher, config.TECHNICAL_RANKING_URL, TECHNICAL_EXTRA_ALIASES, "technical"
    )
    out = []
    for r in rows:
        if not _is_target_market(r.get("market", "")):
            continue
        out.append({
            "code": r.get("code"),
            "name": r.get("name"),
            "market": r.get("market"),
            "price": parse_number(r.get("price")),
            "dev25": parse_number(r.get("dev25")),
            "dev75": parse_number(r.get("dev75")),
            "dev200": parse_number(r.get("dev200")),
            "per": parse_number(r.get("per")),
            "pbr": parse_number(r.get("pbr")),
            "yield": parse_number(r.get("yield")),
        })
    return out


def fetch_credit_data(code, fetcher):
    """
    個別銘柄ページの「信用取引」テーブルから、直近5週分の
    売り残・買い残・倍率を取得する。
    戻り値: {"sell": float|None, "buy": float|None, "ratio": float|None,
             "buy_oldest": float|None} 取得できなければ全てNone。
    """
    url = config.STOCK_PAGE_URL.format(code=code)
    try:
        html = fetcher.get(url, debug_name="stock_{}.html".format(code))
    except Exception:
        return {"sell": None, "buy": None, "ratio": None, "buy_oldest": None}

    soup = BeautifulSoup(html, "lxml")
    required_groups = [
        CREDIT_HEADER_ALIASES["date"],
        CREDIT_HEADER_ALIASES["sell"],
        CREDIT_HEADER_ALIASES["buy"],
    ]
    table, header_texts = find_table_by_headers(soup, required_groups)
    if table is None:
        return {"sell": None, "buy": None, "ratio": None, "buy_oldest": None}

    col = column_index_map(header_texts, CREDIT_HEADER_ALIASES)
    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= max(col.values()):
            continue
        rows.append({
            "date": norm_text(cells[col["date"]].get_text()),
            "sell": parse_number(cells[col["sell"]].get_text()),
            "buy": parse_number(cells[col["buy"]].get_text()),
            "ratio": parse_number(cells[col["ratio"]].get_text()) if "ratio" in col else None,
        })
    if not rows:
        return {"sell": None, "buy": None, "ratio": None, "buy_oldest": None}

    latest = rows[0]
    oldest = rows[-1]
    return {
        "sell": latest["sell"],
        "buy": latest["buy"],
        "ratio": latest["ratio"],
        "buy_oldest": oldest["buy"],
    }


def now_jst_string():
    # サーバー/PCのタイムゾーン設定に依存せず「実行時点のローカル時刻」を返す。
    # 日本のPCで実行する前提のため、基本的にはJSTのローカル時刻と一致する。
    return datetime.now().strftime("%Y年%m月%d日 %H:%M時点")
