# -*- coding: utf-8 -*-
"""
kabutan.jp のスクレイピング処理。

方針: kabutanのHTML構造（class名など）は将来変わりうるため、できるだけ
「見出しセルのテキスト」を手がかりにテーブルと列位置を探す、位置に強い
実装にしている。もし kabutan 側のページ構成が大きく変わった場合は、
ScraperError が分かりやすいメッセージ付きで送出されるので、
data/raw_pages/ に保存された生HTMLを見ながら本ファイルの
*_HEADER_ALIASES を調整してほしい。
"""

import os
import re
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from . import config


class ScraperError(Exception):
    """スクレイピング中に予期しない構造に遭遇した場合に送出する。"""


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})
    return s


def _get(session, url, debug_name=None):
    resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    if debug_name:
        _save_debug_html(debug_name, resp.text)
    return resp.text


def _save_debug_html(name, html):
    try:
        os.makedirs(config.RAW_HTML_DEBUG_DIR, exist_ok=True)
        path = os.path.join(config.RAW_HTML_DEBUG_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    except OSError:
        pass  # デバッグ保存の失敗は致命的ではない


def _norm_text(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)  # 全角数字・記号を半角に寄せる
    return s.strip()


def parse_number(raw):
    """'1,234円' '+12.3%' '－' '3.29倍' などを float/None に変換する。"""
    if raw is None:
        return None
    s = _norm_text(raw)
    if s in ("", "-", "－", "―", "*", "N/A", "--"):
        return None
    s = s.replace(",", "").replace("円", "").replace("倍", "").replace("%", "").replace("株", "")
    s = s.replace("+", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _find_table_by_headers(soup, required_keyword_groups):
    """
    required_keyword_groups: 各要素が「その列に期待される見出し候補文字列のリスト」の
    リスト。全グループについて、いずれかの候補文字列を含む見出しセルを持つ
    <table> を探して返す。見つからなければ None。
    """
    for table in soup.find_all("table"):
        header_cells = table.find_all(["th"])
        if not header_cells:
            first_row = table.find("tr")
            if first_row:
                header_cells = first_row.find_all(["th", "td"])
        header_texts = [_norm_text(c.get_text()) for c in header_cells]
        if not header_texts:
            continue
        ok = True
        for group in required_keyword_groups:
            if not any(any(kw in h for kw in group) for h in header_texts):
                ok = False
                break
        if ok:
            return table, header_texts
    return None, None


def _column_index_map(header_texts, alias_map):
    """alias_map: {論理名: [見出し候補...]} -> {論理名: 列インデックス}"""
    idx = {}
    for logical_name, aliases in alias_map.items():
        found = None
        for i, h in enumerate(header_texts):
            if any(a in h for a in aliases):
                found = i
                break
        if found is None:
            raise ScraperError(
                "列「{}」に対応する見出しが見つかりませんでした（候補: {}）。"
                "kabutan.jpのページ構成が変わった可能性があります。"
                "data/raw_pages/ の生HTMLを確認し、config.pyやscraper.pyの見出し候補を調整してください。".format(
                    logical_name, aliases
                )
            )
        idx[logical_name] = found
    return idx


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


def _fetch_ranking_pages(session, base_url, extra_alias_map, kind_label):
    """ページング付きランキング一覧を全ページ取得し、辞書のリストで返す。"""
    all_rows = []
    seen_codes_first_page = None
    for page in range(1, config.MAX_RANKING_PAGES + 1):
        sep = "&" if "?" in base_url else "?"
        url = base_url if page == 1 else "{}{}page={}".format(base_url, sep, page)
        html = _get(session, url, debug_name="{}_page{}.html".format(kind_label, page))
        soup = BeautifulSoup(html, "lxml")

        required_groups = [
            RANKING_HEADER_ALIASES["code"],
            RANKING_HEADER_ALIASES["name"],
            RANKING_HEADER_ALIASES["market"],
        ]
        table, header_texts = _find_table_by_headers(soup, required_groups)
        if table is None:
            if page == 1:
                raise ScraperError(
                    "{}: ランキング表が見つかりませんでした。kabutan.jpの"
                    "ページ構成が変わっている可能性があります。".format(kind_label)
                )
            break  # 2ページ目以降で見つからない＝最終ページを超えた

        alias_map = dict(RANKING_HEADER_ALIASES)
        alias_map.update(extra_alias_map)
        col = _column_index_map(header_texts, alias_map)

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
                text = _norm_text(cells[i].get_text())
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


def fetch_fundamental_candidates(session=None):
    """通期『営業利益』連続増益ランキングを取得する。"""
    session = session or _session()
    rows = _fetch_ranking_pages(
        session, config.FUNDAMENTAL_RANKING_URL, FUNDAMENTAL_EXTRA_ALIASES, "fundamental"
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


def fetch_technical_candidates(session=None):
    """移動平均線上昇トレンド銘柄ランキングを取得する。"""
    session = session or _session()
    rows = _fetch_ranking_pages(
        session, config.TECHNICAL_RANKING_URL, TECHNICAL_EXTRA_ALIASES, "technical"
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


def fetch_credit_data(code, session=None):
    """
    個別銘柄ページの「信用取引」テーブルから、直近5週分の
    売り残・買い残・倍率を取得する。
    戻り値: {"sell": float|None, "buy": float|None, "ratio": float|None,
             "buy_oldest": float|None} 取得できなければ全てNone。
    """
    session = session or _session()
    url = config.STOCK_PAGE_URL.format(code=code)
    try:
        html = _get(session, url, debug_name="stock_{}.html".format(code))
    except requests.RequestException:
        return {"sell": None, "buy": None, "ratio": None, "buy_oldest": None}

    soup = BeautifulSoup(html, "lxml")
    required_groups = [
        CREDIT_HEADER_ALIASES["date"],
        CREDIT_HEADER_ALIASES["sell"],
        CREDIT_HEADER_ALIASES["buy"],
    ]
    table, header_texts = _find_table_by_headers(soup, required_groups)
    if table is None:
        return {"sell": None, "buy": None, "ratio": None, "buy_oldest": None}

    col = _column_index_map(header_texts, CREDIT_HEADER_ALIASES)
    body = table.find("tbody") or table
    rows = []
    for tr in body.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= max(col.values()):
            continue
        rows.append({
            "date": _norm_text(cells[col["date"]].get_text()),
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
