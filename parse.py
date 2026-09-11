# -*- coding: utf-8 -*-
"""
ランキングページのHTMLから、本命のデータ表を取り出してレコード化するモジュール。

方針：
  - 「コード」列を含むテーブルを本命の表とみなす
  - コード・銘柄名・市場だけを共通列としてDBの列に正規化する
  - それ以外の列（株価・前日比・出来高・PERなど、ページによってバラバラ）は
    まるごとJSON文字列にして extra 列に保存する
    -> ページごとにパーサーを書き分けなくて済む。後でSQLのJSON関数や
       Python側で好きなように取り出せる。
"""

import json
import re
from io import StringIO
import pandas as pd


def extract_stock_name(html: str) -> str | None:
    """個別銘柄ページ（/stock/?code=XXXX）のtitleタグから銘柄名を抜き出す。
    例: '<title>ＭＩＸＩ【2121】株の基本情報｜株探（かぶたん）</title>' -> 'ＭＩＸＩ'
    取れなければNoneを返す。"""
    m = re.search(r"<title>(.*?)【", html)
    return m.group(1).strip() if m else None


def parse_stock_detail(html: str) -> dict:
    """個別銘柄ページ（/stock/?code=XXXX）から主要情報を抜き出す。
    テーブルの並び順は調査済みの構造に依存しているため、サイト側の変更で
    ずれる可能性がある。取れなかった項目はNoneのまま返す。"""
    tables = pd.read_html(StringIO(html))
    result = {
        "per": None, "pbr": None, "yield": None, "margin_ratio": None, "market_cap": None,
        "today": {}, "margin_history": [], "financials": [],
    }

    for df in tables:
        cols = list(df.columns)

        # PER/PBR/利回り/信用倍率 + 時価総額
        if cols == ["PER", "PBR", "利回り", "信用倍率"] and len(df) >= 2:
            result["per"] = _clean_value(df.iloc[0, 0])
            result["pbr"] = _clean_value(df.iloc[0, 1])
            result["yield"] = _clean_value(df.iloc[0, 2])
            result["margin_ratio"] = _clean_value(df.iloc[0, 3])
            result["market_cap"] = _clean_value(df.iloc[1, 2])
            continue

        # 本日の株価情報（始値/高値/安値/終値、出来高/売買代金など、ラベル:値の2列表）
        if df.shape[1] in (2, 4) and df.shape[0] in (3, 4, 10) and 0 in cols:
            for _, row in df.iterrows():
                label = _clean_value(row[0])
                value = _clean_value(row[1]) if 1 in cols else None
                if label and value is not None and label not in result["today"]:
                    result["today"][label] = value
            continue

        # 信用取引の週次推移
        if cols == ["日付", "売り残", "買い残", "倍率"]:
            result["margin_history"] = df.to_dict(orient="records")
            continue

        # 業績推移
        if cols == ["決算期", "売上高", "経常益", "最終益", "１株益", "１株配", "発表日"]:
            result["financials"] = df.to_dict(orient="records")
            continue

    return result


def find_main_table(html: str) -> pd.DataFrame:
    tables = pd.read_html(StringIO(html))
    for df in tables:
        if "コード" in df.columns:
            return df
    raise ValueError("ランキング表(<table>)が見つかりませんでした。サイト構造が変わった可能性があります。")


def _clean_value(val):
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return str(val).strip()


def find_price_history_table(html: str) -> pd.DataFrame | None:
    """kabutan.jp/stock/kabuka?code=XXXX ページから日足四本値の表を取り出す。
    見つからない場合（存在しないコード・ページ末尾など）はNoneを返す。"""
    tables = pd.read_html(StringIO(html))
    for df in tables:
        if "日付" in df.columns and "終値" in df.columns:
            return df
    return None


def _to_iso_date(jp_date: str) -> str | None:
    """'26/02/05' のような表記を '2026-02-05' に変換する。パースできなければNone。"""
    try:
        yy, mm, dd = str(jp_date).strip().split("/")
        year = 2000 + int(yy)
        return f"{year:04d}-{int(mm):02d}-{int(dd):02d}"
    except (ValueError, AttributeError):
        return None


def price_history_to_records(df: pd.DataFrame, code: str) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        date_iso = _to_iso_date(row.get("日付"))
        if date_iso is None:
            continue
        records.append({
            "code": code,
            "date": date_iso,
            "open": _clean_value(row.get("始値")),
            "high": _clean_value(row.get("高値")),
            "low": _clean_value(row.get("安値")),
            "close": _clean_value(row.get("終値")),
            "change": _clean_value(row.get("前日比")),
            "change_pct": _clean_value(row.get("前日比％")),
            "volume": _clean_value(row.get("売買高(株)")),
        })
    return records


def table_to_records(df: pd.DataFrame, ranking_key: str, snapshot_date: str, rank_offset: int = 0) -> list[dict]:
    records = []
    for i, row in df.iterrows():
        code = str(row.get("コード", "")).strip()
        if not code or code.lower() == "nan":
            continue
        name = str(row.get("銘柄名", "")).strip()
        market = str(row.get("市場", "")).strip()

        extra = {}
        for col in df.columns:
            if col in ("コード", "銘柄名", "市場"):
                continue
            extra[str(col)] = _clean_value(row[col])

        records.append({
            "ranking_key": ranking_key,
            "snapshot_date": snapshot_date,
            "rank": rank_offset + i + 1,
            "code": code,
            "name": name,
            "market": market,
            "extra": json.dumps(extra, ensure_ascii=False),
        })
    return records
