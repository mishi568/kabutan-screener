# -*- coding: utf-8 -*-
"""
出来高ランキングの取得（出来高急増ウォッチ専用）。

長期上昇候補スクリーナー(scraper.py)とは別の、完全に独立したスクレイパー。
共通のテーブル解析ロジックは html_utils.py を、ページ取得は browser_fetch.py の
BrowserFetcher を共有するが、扱うページ・データ・保存先(DB)はすべて別物。

★注意★: config.VOLUME_RANKING_URL は未確認の暫定値です。このモジュールは
「コード」「銘柄名」「出来高」に相当する見出しが見つからない場合、
ScraperErrorをわかりやすいメッセージ付きで送出するので、そのメッセージに
従ってconfig.pyのURLやエイリアスを調整してください。
"""

import time

from bs4 import BeautifulSoup

from . import config
from .html_utils import (
    ScraperError,
    norm_text,
    parse_number,
    find_table_by_headers,
    column_index_map,
    optional_column_index,
)

__all__ = ["fetch_volume_ranking"]


REQUIRED_HEADER_ALIASES = {
    "code": ["コード"],
    "name": ["銘柄名", "銘柄"],
    "volume": ["出来高"],
}

OPTIONAL_HEADER_ALIASES = {
    "market": ["市場"],
    "price": ["株価", "現在値"],
    "change_pct": ["前日比", "騰落率"],
}


def fetch_volume_ranking(fetcher):
    """
    出来高ランキング上位を全ページ取得し、辞書のリストで返す。
    各要素: {"code","name","market"(あれば),"price"(あれば),"volume"}
    """
    all_rows = []
    seen_codes_first_page = None

    for page in range(1, config.MAX_VOLUME_RANKING_PAGES + 1):
        base_url = config.VOLUME_RANKING_URL
        sep = "&" if "?" in base_url else "?"
        url = base_url if page == 1 else "{}{}page={}".format(base_url, sep, page)
        html = fetcher.get(url, debug_name="volume_page{}.html".format(page))
        soup = BeautifulSoup(html, "lxml")

        required_groups = [
            REQUIRED_HEADER_ALIASES["code"],
            REQUIRED_HEADER_ALIASES["name"],
            REQUIRED_HEADER_ALIASES["volume"],
        ]
        table, header_texts = find_table_by_headers(soup, required_groups)
        if table is None:
            if page == 1:
                raise ScraperError(
                    "出来高ランキング表が見つかりませんでした。"
                    "config.VOLUME_RANKING_URL が正しいkabutan.jpのページを"
                    "指していない可能性があります（このURLは未確認の暫定値です）。"
                    "ブラウザでkabutan.jpの「出来高ランキング」ページを開き、"
                    "実際のURLをconfig.pyのVOLUME_RANKING_URLに設定し直してください。"
                    "data/raw_pages/volume_page1.html に保存された生HTMLも参考にできます。"
                )
            break

        col = column_index_map(header_texts, REQUIRED_HEADER_ALIASES)
        optional_col = {}
        for name, aliases in OPTIONAL_HEADER_ALIASES.items():
            idx = optional_column_index(header_texts, aliases)
            if idx is not None:
                optional_col[name] = idx

        body = table.find("tbody") or table
        data_rows = [tr for tr in body.find_all("tr") if tr.find("td") is not None]
        if not data_rows:
            break

        page_codes = []
        for tr in data_rows:
            cells = tr.find_all("td")
            max_needed = max(list(col.values()) + list(optional_col.values()))
            if len(cells) <= max_needed:
                continue
            code = norm_text(cells[col["code"]].get_text())
            name = norm_text(cells[col["name"]].get_text())
            volume = parse_number(cells[col["volume"]].get_text())
            row = {"code": code, "name": name, "volume": volume}
            for opt_name, idx in optional_col.items():
                text = norm_text(cells[idx].get_text())
                if opt_name in ("price", "change_pct"):
                    row[opt_name] = parse_number(text)
                else:
                    row[opt_name] = text
            page_codes.append(code)
            all_rows.append(row)

        if page == 1:
            seen_codes_first_page = page_codes
        elif page_codes == seen_codes_first_page:
            all_rows = all_rows[: -len(page_codes)]
            break

        time.sleep(config.REQUEST_DELAY_SEC)

    return all_rows
