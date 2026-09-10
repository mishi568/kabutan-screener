# -*- coding: utf-8 -*-
"""
「出来高急増・株価横ばい」検出ロジック。

直近N回（既定5営業日ぶん、config.VOLUME_LOOKBACK_RUNS）の出来高ランキング
スナップショットを比較し、
  - ウィンドウの最古日と最新日の両方でランキングに登場している銘柄について、
    出来高が大きく増えた（VOLUME_SURGE_RATIO倍以上）のに株価はほぼ動いていない
    （±VOLUME_PRICE_FLAT_PCT%以内）銘柄を「出来高急増・株価横ばい」として検出する
  - 最新日にだけ登場し、ウィンドウ内の他の日には登場していない銘柄は
    「ランキング新規浮上」として別枠で参考表示する（急に出来高が増えた可能性が
    高いが、比較対象がないため倍率・株価変化は計算できない）

「直近N営業日」は暦日ではなく「このツールを実際に成功実行した日」を新しい順に
数える。土日祝日はそもそも実行されない想定のため、毎営業日実行していれば
自動的につじつまが合う。
"""

from . import config


def detect_surges(volume_storage, surge_ratio=None, price_flat_pct=None, lookback_runs=None):
    surge_ratio = config.VOLUME_SURGE_RATIO if surge_ratio is None else surge_ratio
    price_flat_pct = config.VOLUME_PRICE_FLAT_PCT if price_flat_pct is None else price_flat_pct
    lookback_runs = config.VOLUME_LOOKBACK_RUNS if lookback_runs is None else lookback_runs

    dates = volume_storage.get_recent_success_dates(lookback_runs)
    if len(dates) < 2:
        return {
            "window_dates": dates,
            "oldest_date": dates[0] if dates else None,
            "latest_date": dates[0] if dates else None,
            "surges": [],
            "new_entrants": [],
            "insufficient_data": True,
        }

    latest_date = dates[0]
    oldest_date = dates[-1]

    latest_rows = volume_storage.get_ranking_for_run(latest_date)
    oldest_rows = volume_storage.get_ranking_for_run(oldest_date)
    oldest_by_code = {r["code"]: r for r in oldest_rows}

    surges = []
    new_entrants = []

    for r in latest_rows:
        code = r["code"]
        base = oldest_by_code.get(code)

        if base is None:
            new_entrants.append({
                "code": code,
                "name": r.get("name"),
                "market": r.get("market"),
                "rank": r.get("rank"),
                "price": r.get("price"),
                "volume": r.get("volume"),
                "latest_date": latest_date,
            })
            continue

        base_volume = base.get("volume")
        latest_volume = r.get("volume")
        if not base_volume or latest_volume is None:
            continue

        ratio = latest_volume / base_volume
        base_price = base.get("price")
        latest_price = r.get("price")
        price_pct = None
        if base_price and latest_price is not None:
            price_pct = (latest_price - base_price) / base_price * 100.0

        if ratio >= surge_ratio and price_pct is not None and abs(price_pct) <= price_flat_pct:
            surges.append({
                "code": code,
                "name": r.get("name"),
                "market": r.get("market"),
                "volume_ratio": ratio,
                "price_pct_change": price_pct,
                "base_volume": base_volume,
                "latest_volume": latest_volume,
                "base_price": base_price,
                "latest_price": latest_price,
                "base_rank": base.get("rank"),
                "latest_rank": r.get("rank"),
                "base_date": oldest_date,
                "latest_date": latest_date,
            })

    surges.sort(key=lambda x: x["volume_ratio"], reverse=True)
    new_entrants.sort(key=lambda x: (x.get("rank") is None, x.get("rank")))

    return {
        "window_dates": dates,
        "oldest_date": oldest_date,
        "latest_date": latest_date,
        "surge_ratio_threshold": surge_ratio,
        "price_flat_pct_threshold": price_flat_pct,
        "surges": surges,
        "new_entrants": new_entrants,
        "insufficient_data": False,
    }
