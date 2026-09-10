# -*- coding: utf-8 -*-
"""
HTMLテーブル解析の共通ユーティリティ。

kabutan.jp のような外部サイトはCSSのクラス名がいつ変わってもおかしくないため、
「見出しセルの文字列」を手がかりにテーブルと列位置を探す、位置に強い実装を
共通化している。長期上昇候補スクリーナー(scraper.py)と出来高急増ウォッチ
(volume_scraper.py)の両方から使われる。
"""

import re
import unicodedata


class ScraperError(Exception):
    """スクレイピング中に予期しない構造に遭遇した場合に送出する。"""


def norm_text(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)  # 全角数字・記号を半角に寄せる
    return s.strip()


def parse_number(raw):
    """'1,234円' '+12.3%' '－' '3.29倍' などを float/None に変換する。"""
    if raw is None:
        return None
    s = norm_text(raw)
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


def find_table_by_headers(soup, required_keyword_groups):
    """
    required_keyword_groups: 各要素が「その列に期待される見出し候補文字列のリスト」の
    リスト。全グループについて、いずれかの候補文字列を含む見出しセルを持つ
    <table> を探して返す。見つからなければ (None, None)。
    """
    for table in soup.find_all("table"):
        header_cells = table.find_all(["th"])
        if not header_cells:
            first_row = table.find("tr")
            if first_row:
                header_cells = first_row.find_all(["th", "td"])
        header_texts = [norm_text(c.get_text()) for c in header_cells]
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


def optional_column_index(header_texts, aliases):
    """
    見つかれば列インデックス、見つからなければ None を返す（column_index_mapと違い例外にしない）。
    ページによって存在したりしなかったりする列（市場区分など）向け。
    """
    for i, h in enumerate(header_texts):
        if any(a in h for a in aliases):
            return i
    return None


def column_index_map(header_texts, alias_map):
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
                "kabutan.jpのページ構成が変わったか、URLが想定と違う可能性があります。"
                "data/raw_pages/ の生HTMLを確認し、設定や見出し候補を調整してください。".format(
                    logical_name, aliases
                )
            )
        idx[logical_name] = found
    return idx
