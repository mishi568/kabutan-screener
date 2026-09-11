# -*- coding: utf-8 -*-
"""
マクロ・需給データ(株探以外のデータ源)の日次同期メインスクリプト。

- JPX公式: 空売り集計・投資部門別売買動向・個別銘柄信用取引残高・
  機関投資家の個別銘柄空売りポジション(0.5%以上)
- EDINET: 大量保有報告書(5%以上)
- nikkei225jp.com: PER/PBR・投資主体別売買状況・信用残高・空売り比率・
  騰落レシオ・NT倍率・裁定買い残・先物週次建玉・恐怖指数

run_daily.py(株探ランキング)とは独立して実行する。

各データ源は「今日すでに実行済みか」をmacro_sync_logで記録し、二重実行を
自動でスキップする(特にnikkei225jp.comはPlaywrightでの取得に1分前後かかるため)。
ボタン連打で何度動かしても無駄なアクセスが増えない。強制的に取り直したい
場合は --force を付ける。

使い方:
  python run_macro_sync.py
  python run_macro_sync.py --force   # 今日すでに実行済みでも強制的に再取得する
"""
import argparse
import datetime
from pathlib import Path

import db
import edinet_sync
import jpx_import
import jpx_sync
import nikkei225jp_sync


def _already_run_today(conn, source: str, force: bool) -> bool:
    if force:
        return False
    today = datetime.date.today().isoformat()
    return db.get_last_macro_sync(conn, source) == today


def sync_jpx(conn, force: bool = False) -> None:
    print("=== JPX公式データ ===")
    if _already_run_today(conn, "jpx", force):
        print("  本日は取得済みのためスキップします（--forceで強制再取得できます）")
        return

    fetch_result = jpx_sync.sync_all(cache_dir=Path("jpx_cache"))

    for key in ("short_selling", "margin_positions", "investor_trends", "short_positions"):
        sub = fetch_result[key]
        if not sub["success"]:
            print(f"  [{key}] 取得失敗: {sub.get('error')}")
            continue
        for filepath in sub["files"]:
            result = jpx_import.import_file(conn, filepath)
            if result["success"]:
                print(f"  [OK] {result['message']}")
            else:
                print(f"  [NG] 取込失敗 ({filepath}): {result['error']}")

    db.set_last_macro_sync(conn, "jpx", datetime.date.today().isoformat())


def sync_edinet(conn, force: bool = False) -> None:
    print("=== EDINET大量保有報告書 ===")
    if _already_run_today(conn, "edinet", force):
        print("  本日は取得済みのためスキップします（--forceで強制再取得できます）")
        return

    result = edinet_sync.sync(conn)
    for msg in result["messages"]:
        print(f"  {msg}")

    if result["success"]:
        db.set_last_macro_sync(conn, "edinet", datetime.date.today().isoformat())


def sync_nikkei225jp(conn, force: bool = False) -> None:
    print("=== nikkei225jp.com マクロデータ ===")
    if _already_run_today(conn, "nikkei225jp", force):
        print("  本日は取得済みのためスキップします（--forceで強制再取得できます）")
        return

    result = nikkei225jp_sync.sync_all(conn)
    for key, sub in result.items():
        if sub["success"]:
            print(f"  [OK] {sub['message']}")
        else:
            print(f"  [NG] [{key}] 取得失敗: {sub.get('error')}")

    db.set_last_macro_sync(conn, "nikkei225jp", datetime.date.today().isoformat())


def run(force: bool = False) -> None:
    conn = db.get_conn()
    try:
        sync_jpx(conn, force=force)
        sync_edinet(conn, force=force)
        sync_nikkei225jp(conn, force=force)
    finally:
        conn.close()
    print("\n完了")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="本日すでに取得済みでも強制的に再取得する")
    args = parser.parse_args()
    run(force=args.force)
