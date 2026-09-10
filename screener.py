#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
長期上昇候補スクリーナー（ローカル実行版）

実行すると:
  1. 株探(kabutan.jp)からファンダメンタルズ／テクニカルの候補ランキングを取得
  2. 両方に共通する銘柄について、個別ページから信用取引（需給）データを取得
  3. パーセンタイル順位方式でスコアを算出（Claudeとの会話で決めたのと同じ重み）
  4. data/screener.db に結果を蓄積
  5. output/report.html （ブラウザで見るランキング＋実行ログ）
     output/summary_latest.json （Claudeに貼って確認してもらう用の要約）
     を生成する

使い方:
  python screener.py
  python screener.py --refresh-credit   # 信用取引データのキャッシュを無視して全銘柄再取得
  もしくは Windows なら run.bat をダブルクリック。
"""

import argparse
import os
import sys
import time
import traceback
from datetime import datetime

from kabutan_screener import config, scraper, scoring, storage, report, logsetup
from kabutan_screener.browser_fetch import BrowserFetcher


def _today_str():
    return datetime.now().strftime("%Y-%m-%d")


def _now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_args():
    p = argparse.ArgumentParser(description="長期上昇候補スクリーナー（ローカル実行版）")
    p.add_argument(
        "--refresh-credit", action="store_true",
        help="信用取引（需給）データのキャッシュを無視し、候補銘柄すべてを再取得する",
    )
    return p.parse_args()


def run():
    args = _parse_args()
    date = _today_str()
    ran_at = _now_iso()

    orig_stdout, orig_stderr, log_file = logsetup.start_logging(config.SCREENER_LOG_PATH)
    try:
        return _run_inner(args, date, ran_at)
    finally:
        print("ログ: logs/screener_log.txt （画面が読めなかった場合はこちらを確認してください）")
        logsetup.stop_logging(orig_stdout, orig_stderr, log_file)


def _run_inner(args, date, ran_at):
    print("=== 長期上昇候補スクリーナー ===")
    print("実行日時:", ran_at)

    try:
        print("（初回のみ）ブラウザ(Chromium)を起動しています...")
        with BrowserFetcher() as fetcher:
            print("[1/4] ファンダメンタルズ候補（連続増益ランキング）を取得中...")
            fundamental = scraper.fetch_fundamental_candidates(fetcher)
            print("      {}件".format(len(fundamental)))

            print("[2/4] テクニカル候補（移動平均線上昇トレンド）を取得中...")
            technical = scraper.fetch_technical_candidates(fetcher)
            print("      {}件".format(len(technical)))

            merged = scoring.intersect_candidates(fundamental, technical)
            print("      両方に共通する候補: {}件".format(len(merged)))

            if not merged:
                raise RuntimeError(
                    "候補が0件でした。kabutan.jpのページ構成が変わった可能性があります。"
                    "data/raw_pages/ の生HTMLを確認してください。"
                )

            max_age = 0 if args.refresh_credit else config.CREDIT_CACHE_MAX_AGE_DAYS
            print(
                "[3/4] 個別銘柄の信用取引（需給）データを取得中...（{}銘柄 / キャッシュ有効期限 {}日{}）".format(
                    len(merged), config.CREDIT_CACHE_MAX_AGE_DAYS,
                    "・強制再取得" if args.refresh_credit else "",
                )
            )
            cache_hits = 0
            fetched = 0
            for i, rec in enumerate(merged, start=1):
                cached = storage.get_cached_credit(rec["code"], max_age)
                if cached:
                    rec["credit"] = cached
                    cache_hits += 1
                else:
                    rec["credit"] = scraper.fetch_credit_data(rec["code"], fetcher)
                    storage.save_cached_credit(rec["code"], rec["credit"], _now_iso())
                    fetched += 1
                    time.sleep(config.CREDIT_REQUEST_DELAY_SEC)
                if i % 20 == 0 or i == len(merged):
                    print("      {}/{}（キャッシュ利用 {}件 / 新規取得 {}件）".format(i, len(merged), cache_hits, fetched))

        print("[4/4] スコアを算出し、保存しています...")
        scored = scoring.compute_scores(merged)
        as_of = scraper.now_jst_string()

        storage.save_stocks(date, scored)
        top = scored[0]
        summary_text = "候補{}銘柄を取得しスコアを算出しました（首位: {} {}点）".format(
            len(scored), top["name"], top["score"]
        )
        storage.save_run(
            date, ran_at, "success", summary_text,
            stock_count=len(scored), top_code=top["code"], top_name=top["name"], top_score=top["score"],
        )

        prev_date = storage.get_latest_success_date(before_date=date)
        prev_stocks = storage.get_stocks_for_run(prev_date) if prev_date else []

        summary_json = report.build_summary_json(as_of, scored, prev_stocks, "success")
        report.write_summary_json(os.path.join(config.OUTPUT_DIR, "summary_latest.json"), summary_json)

        recent_runs = storage.get_recent_runs(14)
        report.write_html_report(os.path.join(config.OUTPUT_DIR, "report.html"), as_of, scored, recent_runs)

        print()
        print("完了: 候補{}銘柄 / 首位 {}（{}点）".format(len(scored), top["name"], top["score"]))
        print("需給データ: キャッシュ利用 {}件 / 新規取得 {}件".format(cache_hits, fetched))
        print("レポート: output/report.html")
        print("要約JSON: output/summary_latest.json （Claudeに貼って確認してもらってください）")
        return 0

    except Exception as e:
        traceback.print_exc()
        error_message = "{}".format(e)[:300]
        storage.save_run(date, ran_at, "error", error_message)

        # 今回は失敗しても、前回成功時点のデータでレポートだけは見られるようにしておく
        try:
            latest_date = storage.get_latest_success_date()
            stocks = storage.get_stocks_for_run(latest_date) if latest_date else []
            recent_runs = storage.get_recent_runs(14)
            as_of = "（今回はエラーのため更新できませんでした。表示は前回成功時点のデータです）"
            report.write_html_report(os.path.join(config.OUTPUT_DIR, "report.html"), as_of, stocks, recent_runs)
        except Exception:
            pass

        print()
        print("エラーが発生しました:", error_message)
        print("output/report.html の実行ログ、data/raw_pages/ の生HTMLも確認してみてください。")
        return 1


if __name__ == "__main__":
    sys.exit(run())
