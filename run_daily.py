# -*- coding: utf-8 -*-
"""
毎日1回実行するメインスクリプト。
config.RANKINGS に登録された各ページを、リクエスト間に数秒〜数秒のランダムな
間隔を空けながら順番に取得し、SQLiteに保存する。

Windowsでのスケジュール実行例（タスクスケジューラ）：
  プログラム: C:\\python\\python.exe
  引数      : C:\\Users\\mishi\\Desktop\\Project\\kabutan-screener\\run_daily.py
  開始       : プロジェクトのフォルダ
  トリガー   : 毎日 15:45（大引け後）など
"""

import argparse
import time
import random
import datetime

from config import RANKINGS
from fetch import fetch_html
from parse import find_main_table, table_to_records
from db import get_conn, upsert_ranking_def, upsert_stock, insert_snapshot_records, get_last_sync, set_last_sync


def fetch_ranking(info: dict) -> list:
    """1ランキング分（複数ページ対応）を取得してレコードのリストを返す。"""
    max_pages = info.get("max_pages", 1)
    all_records = []
    rank_offset = 0

    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(random.uniform(2, 4))  # 同一ランキング内のページ間は短めの間隔

        url = info["url"].format(page=page) if "{page}" in info["url"] else info["url"]
        html = fetch_html(url)
        df = find_main_table(html)

        if df is None or df.empty:
            break

        page_records = table_to_records(df, info["_ranking_key"], info["_snapshot_date"], rank_offset=rank_offset)
        all_records.extend(page_records)
        rank_offset += len(df)

        if len(df) == 0:  # 念のため：空ページに到達したら打ち切り
            break

    return all_records


def run(target_date: str | None = None, force: bool = False):
    today = target_date or datetime.date.today().isoformat()
    conn = get_conn()

    # target_dateが明示的に指定された場合(過去データの手動バックフィル)はスキップ判定をしない。
    # 「本日分」として動く通常実行のときだけ、既に本日実行済みなら自動でスキップする。
    if target_date is None and not force and get_last_sync(conn, "kabutan_daily") == today:
        print(f"本日（{today}）は取得済みのためスキップします（--forceで強制再取得できます）")
        conn.close()
        return

    total_ok, total_ng = 0, 0
    items = list(RANKINGS.items())

    for i, (ranking_key, info) in enumerate(items):
        if i > 0:
            wait = random.uniform(3, 6)  # ランキング間は必ず数秒空ける（マナー）
            time.sleep(wait)

        n_pages = info.get("max_pages", 1)
        pages_note = f"（{n_pages}ページ）" if n_pages > 1 else ""
        print(f"[{ranking_key}] {info['title']}{pages_note} -> {info['url']}")
        upsert_ranking_def(conn, ranking_key, info["category"], info["title"], info["url"])

        try:
            info_with_ctx = {**info, "_ranking_key": ranking_key, "_snapshot_date": today}
            records = fetch_ranking(info_with_ctx)
        except Exception as e:
            print(f"  [NG] 取得/解析に失敗: {e}")
            total_ng += 1
            continue

        for r in records:
            upsert_stock(conn, r["code"], r["name"], r["market"], today)
        insert_snapshot_records(conn, records)
        conn.commit()

        print(f"  [OK] {len(records)} 件保存")
        total_ok += 1

    if target_date is None:
        set_last_sync(conn, "kabutan_daily", today)

    conn.close()
    print(f"\n完了: 成功 {total_ok} / 失敗 {total_ng} (対象日: {today})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?", default=None, help="YYYY-MM-DDで過去日付を指定（過去データの手動投入用、省略時は本日）")
    parser.add_argument("--force", action="store_true", help="本日すでに取得済みでも強制的に再取得する")
    args = parser.parse_args()
    run(args.date, force=args.force)
