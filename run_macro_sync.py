# -*- coding: utf-8 -*-
"""
マクロ・需給データ(株探以外のデータ源)の日次同期メインスクリプト。

- JPX公式: 空売り集計・投資部門別売買動向・個別銘柄信用取引残高・
  機関投資家の個別銘柄空売りポジション(0.5%以上)
- EDINET: 大量保有報告書(5%以上)
- nikkei225jp.com: PER/PBR・投資主体別売買状況・信用残高・空売り比率・
  騰落レシオ・NT倍率・裁定買い残・先物週次建玉・恐怖指数

run_daily.py(株探ランキング)とは独立して実行する。

使い方:
  python run_macro_sync.py
"""
from pathlib import Path

import db
import edinet_sync
import jpx_import
import jpx_sync
import nikkei225jp_sync


def sync_jpx(conn) -> None:
    print("=== JPX公式データ ===")
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


def sync_edinet(conn) -> None:
    print("=== EDINET大量保有報告書 ===")
    result = edinet_sync.sync(conn)
    for msg in result["messages"]:
        print(f"  {msg}")


def sync_nikkei225jp(conn) -> None:
    print("=== nikkei225jp.com マクロデータ ===")
    result = nikkei225jp_sync.sync_all(conn)
    for key, sub in result.items():
        if sub["success"]:
            print(f"  [OK] {sub['message']}")
        else:
            print(f"  [NG] [{key}] 取得失敗: {sub.get('error')}")


def run() -> None:
    conn = db.get_conn()
    try:
        sync_jpx(conn)
        sync_edinet(conn)
        sync_nikkei225jp(conn)
    finally:
        conn.close()
    print("\n完了")


if __name__ == "__main__":
    run()
