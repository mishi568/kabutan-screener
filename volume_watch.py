#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
出来高急増ウォッチ（ローカル実行版）

長期上昇候補スクリーナー(screener.py)とは完全に別の、独立したツールです。
別のデータベース(data/volume_watch.db)・別のレポート(output/volume_report.html,
output/volume_summary_latest.json)を使います。

実行すると:
  1. 株探(kabutan.jp)の出来高ランキング上位を取得
  2. その日のスナップショットとして data/volume_watch.db に蓄積
  3. 直近{N}営業日（このツールを実際に実行した日ベース。config.VOLUME_LOOKBACK_RUNS）の
     最古日と最新日を比較し、「出来高が急増したのに株価が横ばいの銘柄」を検出
  4. output/volume_report.html （ブラウザで見るランキング＋実行ログ）
     output/volume_summary_latest.json （Claudeに貼って確認してもらう用の要約）
     を生成する

使い方:
  python volume_watch.py
  もしくは Windows なら run_volume.bat をダブルクリック。

★注意★: config.VOLUME_RANKING_URL（出来高ランキングページのURL）は
未確認の暫定値です。エラーになる場合はREADME.mdの説明に従って修正してください。
毎営業日続けて実行しないと「直近N営業日」の比較が正しく機能しません。
"""

import os
import sys
import traceback
from datetime import datetime

from kabutan_screener import config, volume_scraper, volume_storage, volume_analysis, volume_report
from kabutan_screener.browser_fetch import BrowserFetcher


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _write_report_from_current_state(as_of):
    analysis = volume_analysis.detect_surges(volume_storage)
    recent_runs = volume_storage.get_recent_runs(14)
    volume_report.write_html_report(
        os.path.join(config.OUTPUT_DIR, "volume_report.html"), as_of, analysis, recent_runs
    )
    summary = volume_report.build_summary_json(as_of, analysis, recent_runs[0]["status"] if recent_runs else "success")
    volume_report.write_summary_json(
        os.path.join(config.OUTPUT_DIR, "volume_summary_latest.json"), summary
    )
    return analysis


def run():
    date = _today_str()
    ran_at = _now_iso()

    print("=== 出来高急増ウォッチ ===")
    print("実行日時:", ran_at)

    try:
        print("（初回のみ）ブラウザ(Chromium)を起動しています...")
        with BrowserFetcher() as fetcher:
            print("[1/2] 出来高ランキングを取得中...")
            rows = volume_scraper.fetch_volume_ranking(fetcher)
            print("      {}件".format(len(rows)))

        if not rows:
            raise RuntimeError(
                "出来高ランキングが0件でした。config.VOLUME_RANKING_URL が正しいkabutan.jpの"
                "ページを指していない可能性があります（このURLは未確認の暫定値です）。"
                "README.mdの「出来高ランキングのURLについて」を確認してください。"
            )

        for i, r in enumerate(rows, start=1):
            r["rank"] = i

        print("[2/2] データベースに保存し、直近{}営業日と比較しています...".format(config.VOLUME_LOOKBACK_RUNS))
        volume_storage.save_ranking(date, rows)
        summary_text = "出来高ランキング{}件を取得・蓄積しました。".format(len(rows))
        volume_storage.save_run(date, ran_at, "success", summary_text, stock_count=len(rows))

        as_of = datetime.now().strftime("%Y年%m月%d日 %H:%M時点")
        analysis = _write_report_from_current_state(as_of)

        print()
        if analysis["insufficient_data"]:
            print("完了: データを蓄積しました（比較にはあと{}回以上の実行が必要です）".format(
                max(0, 2 - len(analysis["window_dates"]))
            ))
        else:
            print("完了: 出来高急増・株価横ばい候補 {}件 / ランキング新規浮上 {}件".format(
                len(analysis["surges"]), len(analysis["new_entrants"])
            ))
        print("レポート: output/volume_report.html")
        print("要約JSON: output/volume_summary_latest.json （Claudeに貼って確認してもらってください）")
        return 0

    except Exception as e:
        traceback.print_exc()
        error_message = "{}".format(e)[:300]
        volume_storage.save_run(date, ran_at, "error", error_message)

        try:
            as_of = "（今回はエラーのため更新できませんでした。表示は前回までの蓄積データです）"
            _write_report_from_current_state(as_of)
        except Exception:
            pass

        print()
        print("エラーが発生しました:", error_message)
        print("output/volume_report.html の実行ログ、data/raw_pages/ の生HTMLも確認してみてください。")
        return 1


if __name__ == "__main__":
    sys.exit(run())
