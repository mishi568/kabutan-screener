# -*- coding: utf-8 -*-
"""EDINET API v2 大量保有報告書(5%ルール)自動取得エンジン

金融庁のEDINET APIを利用して、大量保有報告書・変更報告書のメタデータを取得し、
保有割合の増減や提出者(機関名)を抽出してDBに保存する。

APIキーは引数、なければ環境変数 EDINET_API_KEY から取得する。
"""
import os
import re
import time
from datetime import datetime, timedelta

import requests

import db

EDINET_API_BASE = "https://api.edinet-fsa.go.jp/api/v2"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) kabutan-screener/1.0"
REQUEST_TIMEOUT = 20
LARGE_HOLDING_DOC_TYPE = "350"  # 大量保有報告書・変更報告書


def get_api_key(explicit: str | None = None) -> str | None:
    """APIキーを取得する(引数 > 環境変数 EDINET_API_KEY の優先順)"""
    return explicit or os.environ.get("EDINET_API_KEY")


def has_api_key(api_key: str | None) -> bool:
    return bool(api_key and api_key.strip())


def should_sync(conn, api_key: str | None) -> bool:
    """同期が必要か判定する。APIキー未設定・土日・本日既に同期済みならFalse"""
    if not has_api_key(api_key):
        return False
    if datetime.now().weekday() >= 5:
        return False
    last_date = db.get_latest_edinet_date(conn)
    return last_date != datetime.now().strftime("%Y-%m-%d")


def _extract_holding_info(doc: dict) -> dict | None:
    """EDINET APIレスポンスの1件のドキュメントから大量保有情報を抽出する"""
    doc_id = doc.get("docID", "")
    if not doc_id:
        return None

    filer_name = doc.get("filerName", "")
    if not filer_name:
        return None

    # secCodeは「提出者(=保有者・報告書を出した側)」自身の証券コードで、
    # 提出者が上場企業の場合のみ入る(例: Ａｂａｌａｎｃｅ株式会社が他社株を
    # 5%以上保有して提出者になったケース)。この報告書が「どの銘柄について」の
    # ものかとは無関係なので、対象銘柄コードとしては使わない。
    doc_title = doc.get("docDescription", "")
    report_type = "変更報告書" if "変更" in doc_title else "大量保有報告書"

    holding_ratio = None
    if doc_title:
        ratio_matches = re.findall(r"(\d+\.?\d*)\s*[%％]", doc_title)
        if ratio_matches:
            holding_ratio = float(ratio_matches[0])

    # subjectEdinetCode: 大量保有報告書(docTypeCode=350)のみ設定される「対象
    # (=保有される側の発行会社)」のEDINETコード。これが「どの銘柄についての
    # 報告か」を表す。edinetCodeは提出者(保有者)自身のコードで対象銘柄とは
    # 無関係なため、subjectEdinetCodeが無い異常系のフォールバックにのみ使う。
    # ※EDINETの書類一覧APIは対象銘柄の証券コード/会社名そのものは返さないため、
    # ここではEDINETコード(E+5桁)のまま保存する。4桁の証券コードや会社名に
    # 変換するには別途EDINETコードリストとの突合が必要(未対応)。
    issuer_name = doc.get("subjectEdinetCode", "") or doc.get("edinetCode", "")

    filing_date = doc.get("submitDateTime", "")
    if filing_date:
        filing_date = filing_date[:10]  # "2026-01-15 09:00:00" -> "2026-01-15"

    return {
        "doc_id": doc_id,
        "date": filing_date,
        "submission_date": filing_date,
        # 対象銘柄の4桁証券コードはEDINETの書類一覧APIからは取得できないため
        # 現状Noneのまま(issuer_nameのEDINETコードで対象銘柄を判別する)。
        "code": None,
        "issuer_name": issuer_name,
        "holder_name": filer_name,
        "holding_ratio": holding_ratio,
        "report_type": report_type,
        "purpose": doc_title,
    }


def fetch_documents_for_date(date_str: str, api_key: str, session: requests.Session | None = None) -> list[dict]:
    """指定日の提出書類一覧を取得し、大量保有報告書(docTypeCode=350)のみ抽出する"""
    session = session or requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)

    params = {"date": date_str, "type": 2, "Subscription-Key": api_key}
    try:
        resp = session.get(f"{EDINET_API_BASE}/documents.json", params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if data.get("metadata", {}).get("status") != "200":
        return []

    records = []
    for doc in data.get("results", []):
        if str(doc.get("docTypeCode", "")) == LARGE_HOLDING_DOC_TYPE:
            rec = _extract_holding_info(doc)
            if rec:
                records.append(rec)
    return records


def sync(conn, api_key: str | None = None, days_back: int | None = None) -> dict:
    """過去days_back日分の大量保有報告書を取得しDBへ保存する。

    days_back未指定時: 初回同期(DBが空)なら30日分、以降は7日分。
    """
    api_key = get_api_key(api_key)
    result = {"success": False, "records_count": 0, "messages": []}

    if not has_api_key(api_key):
        result["messages"].append("EDINET APIキーが設定されていません(環境変数 EDINET_API_KEY)。")
        return result

    if days_back is None:
        days_back = 30 if db.get_latest_edinet_date(conn) is None else 7

    session = requests.Session()
    session.headers.setdefault("User-Agent", USER_AGENT)

    all_records = []
    today = datetime.now().date()
    for i in range(days_back):
        target_date = today - timedelta(days=i)
        if target_date.weekday() >= 5:  # 土日はスキップ
            continue
        all_records.extend(fetch_documents_for_date(target_date.strftime("%Y-%m-%d"), api_key, session))
        time.sleep(0.5)  # APIへの配慮(polite delay)

    for rec in all_records:
        db.upsert_record(conn, "edinet_large_holdings", ("doc_id",), rec)
    conn.commit()

    result["success"] = True
    result["records_count"] = len(all_records)
    result["messages"].append(
        f"EDINET大量保有報告書: {len(all_records)}件を取得・保存しました" if all_records
        else "EDINET: 該当する大量保有報告書は見つかりませんでした"
    )
    return result


if __name__ == "__main__":
    conn = db.get_conn()
    result = sync(conn)
    for msg in result["messages"]:
        print(msg)
    conn.close()
