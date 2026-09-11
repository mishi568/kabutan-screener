# -*- coding: utf-8 -*-
"""
シグナル別の勝率バックテスト（アクセスなし、DBの集計だけ）。

「あるシグナルが出た銘柄は、その後の株価がどう動いたか」を ranking_snapshots と
price_history を突き合わせて集計する。判定ルールは2種類から選べる：

  rule="max_high" : シグナル発生からhorizon_days営業日以内の最高値が、発生日終値比
                     threshold_pct%以上なら勝ち（例: 5営業日以内に+5%）
  rule="close"     : シグナル発生からhorizon_days営業日後の終値が、発生日終値比
                     threshold_pct%以上なら勝ち（例: 20営業日後にプラス = threshold_pct=0）

price_historyに judge に必要な期間分のデータが無い場合（対象銘柄を取得していない／
シグナル発生からまだ日数が経っていない）は「判定不能」として集計から除外する。
つまり運用を続けて price_history が溜まるほど、判定可能な件数が増えていく。

地合い（日経平均などの同期間の値動き）も同じロジックで計算し、各シグナルの平均値として
併記する（fetch_market_index.py で事前に指数データを取得しておく必要がある）。

使い方:
  python backtest.py --horizon 20 --rule close --threshold 0
  python backtest.py --horizon 5 --rule max_high --threshold 5
"""

import argparse
import numpy as np
import pandas as pd

from db import get_conn

TARGET_PRESETS = {
    "5営業日以内の最高値+5%": {"horizon_days": 5, "rule": "max_high", "threshold_pct": 5.0},
    "20営業日後の終値プラス": {"horizon_days": 20, "rule": "close", "threshold_pct": 0.0},
}

MARKET_INDEX_CODE_DEFAULT = "0000"  # 日経平均株価（config.MARKET_INDICES参照）


def _load_price_by_code(conn) -> dict:
    df = pd.read_sql_query("SELECT code, date, close, high FROM price_history ORDER BY code, date", conn)
    return {code: g.reset_index(drop=True) for code, g in df.groupby("code")}


def compute_price_moves(price_by_code: dict, codes_dates: set, horizon_days: int, rule: str, threshold_pct: float) -> pd.DataFrame:
    """指定した(code, date)の組ごとに、その日からhorizon_days営業日先までの値動きを計算する。
    先の営業日分のデータがまだ無いものは「判定不能」として結果から除外する。"""
    rows = []
    for code, date in codes_dates:
        g = price_by_code.get(code)
        if g is None:
            continue
        idx = g.index[g["date"] == date]
        if len(idx) == 0:
            continue
        i = idx[0]
        entry_close = g.loc[i, "close"]
        if not entry_close:
            continue
        future = g.loc[i + 1: i + horizon_days]
        if len(future) < horizon_days:
            continue  # 判定に必要な先の営業日分のデータがまだ無い

        if rule == "max_high":
            metric = (future["high"].max() - entry_close) / entry_close * 100
        else:  # "close"
            metric = (future["close"].iloc[-1] - entry_close) / entry_close * 100

        rows.append({
            "code": code, "date": date, "entry_close": entry_close,
            "metric_pct": metric, "win": bool(metric >= threshold_pct),
        })
    return pd.DataFrame(rows)


def signal_win_rates(conn, horizon_days: int = 20, rule: str = "close", threshold_pct: float = 0.0,
                      ranking_keys: list | None = None, market_index_code: str = MARKET_INDEX_CODE_DEFAULT):
    """ranking_key（シグナル）別の勝率サマリーと、明細行(merged)を返す。
    判定可能な実績が無い場合は (空のDataFrame, 空のDataFrame) を返す。"""
    query = "SELECT DISTINCT ranking_key, snapshot_date, code FROM ranking_snapshots"
    params: tuple = ()
    if ranking_keys:
        placeholders = ",".join("?" for _ in ranking_keys)
        query += f" WHERE ranking_key IN ({placeholders})"
        params = tuple(ranking_keys)
    snaps = pd.read_sql_query(query, conn, params=params)
    if snaps.empty:
        return pd.DataFrame(), pd.DataFrame()

    price_by_code = _load_price_by_code(conn)
    codes_dates = set(zip(snaps["code"], snaps["snapshot_date"]))
    moves = compute_price_moves(price_by_code, codes_dates, horizon_days, rule, threshold_pct)
    if moves.empty:
        return pd.DataFrame(), moves

    merged = snaps.merge(moves, left_on=["code", "snapshot_date"], right_on=["code", "date"])

    # 地合い：同じ期間・同じルールでの指数の値動きを突き合わせる
    index_dates = {(market_index_code, d) for d in merged["date"].unique()}
    index_moves = compute_price_moves(price_by_code, index_dates, horizon_days, rule, threshold_pct)
    if not index_moves.empty:
        index_map = dict(zip(index_moves["date"], index_moves["metric_pct"]))
        merged["market_metric_pct"] = merged["date"].map(index_map)
    else:
        merged["market_metric_pct"] = np.nan

    summary = (
        merged.groupby("ranking_key")
        .agg(
            件数=("win", "size"),
            勝率=("win", "mean"),
            平均リターン=("metric_pct", "mean"),
            平均地合い=("market_metric_pct", "mean"),
        )
        .reset_index()
    )
    summary["勝率(%)"] = (summary["勝率"] * 100).round(1)
    summary["平均リターン(%)"] = summary["平均リターン"].round(2)
    summary["平均地合い(%)"] = summary["平均地合い"].round(2)
    summary = summary.drop(columns=["勝率", "平均リターン", "平均地合い"])
    summary = summary.sort_values("勝率(%)", ascending=False).reset_index(drop=True)

    return summary, merged


def combo_win_rate(merged: pd.DataFrame, key_a: str, key_b: str) -> dict:
    """2つのシグナルが同日重複して出現した銘柄だけに絞った勝率を計算する。"""
    rows_a = merged[merged["ranking_key"] == key_a]
    rows_b = merged[merged["ranking_key"] == key_b]
    set_a = set(zip(rows_a["code"], rows_a["date"]))
    set_b = set(zip(rows_b["code"], rows_b["date"]))
    both = set_a & set_b
    if not both:
        return {"件数": 0, "勝率(%)": None, "平均リターン(%)": None}

    sub = merged[merged.apply(lambda r: (r["code"], r["date"]) in both, axis=1)]
    sub = sub.drop_duplicates(subset=["code", "date"])
    return {
        "件数": len(sub),
        "勝率(%)": round(sub["win"].mean() * 100, 1),
        "平均リターン(%)": round(sub["metric_pct"].mean(), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="シグナル別勝率バックテスト")
    parser.add_argument("--horizon", type=int, default=20, help="判定期間（営業日数）")
    parser.add_argument("--rule", choices=["max_high", "close"], default="close",
                         help="max_high=期間内の最高値で判定 / close=期間後の終値で判定")
    parser.add_argument("--threshold", type=float, default=0.0, help="勝ち判定の閾値（%）")
    args = parser.parse_args()

    conn = get_conn()
    summary, _merged = signal_win_rates(conn, args.horizon, args.rule, args.threshold)
    conn.close()

    if summary.empty:
        print("判定可能な実績がまだありません。price_history / ranking_snapshots が十分に"
              "溜まってから再度お試しください（シグナル発生日から判定期間分の株価データが必要です）。")
        return

    print(f"判定ルール: horizon={args.horizon}営業日 / rule={args.rule} / threshold={args.threshold}%\n")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
