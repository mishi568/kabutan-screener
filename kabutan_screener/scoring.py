# -*- coding: utf-8 -*-
"""
スコアリング処理。

Claudeとの会話で作った「長期上昇候補スクリーナー」と同じ考え方:
各指標を候補銘柄集団内でのパーセンタイル順位（0〜100点、高いほど良い）に
変換し、以下の重みで合成する。

- ファンダメンタルズ 40%: 連続増益期数35% + 今期予想増益率40% + 増益期間平均増益率25%
- テクニカル 35%: 25日線カイリ率25% + 75日線カイリ率35% + 200日線カイリ率40%
- 割安度 10%: PERの低さ（低いほど加点）
- 需給 15%: 信用倍率（低いほど加点）。売り残ゼロの「買い長」銘柄は
  直近の信用買い残増減率から代替評価する。
"""

from . import config


def percentile_ranks(values, higher_is_better=True):
    """
    values: [(key, number_or_None), ...]
    戻り値: {key: score(0-100)}  Noneの要素は50点（中立）を返す。
    同値はタイの平均順位を使う。
    """
    valid = [(k, v) for k, v in values if v is not None]
    scores = {k: 50.0 for k, _ in values}  # デフォルト＝中立
    n = len(valid)
    if n <= 1:
        for k, _ in valid:
            scores[k] = 50.0
        return scores

    sorted_vals = sorted(v for _, v in valid)

    def rank_of(x):
        # タイは平均順位（0-indexed）にする
        lo = 0
        hi = n
        # 最初の位置
        import bisect
        left = bisect.bisect_left(sorted_vals, x)
        right = bisect.bisect_right(sorted_vals, x)
        return (left + right - 1) / 2.0

    for k, v in valid:
        r = rank_of(v)  # 0 (最小) 〜 n-1 (最大)
        pct = r / (n - 1) * 100.0
        if not higher_is_better:
            pct = 100.0 - pct
        scores[k] = pct
    return scores


def compute_supply_demand(records):
    """
    records: [{"code":..., "credit": {"sell","buy","ratio","buy_oldest"}}, ...]
    戻り値: {code: {"category": "r"/"b"/"n", "ratio": float|None,
                    "buy_change_pct": float|None, "score": float}}
    """
    ratio_pairs = []
    result = {}
    for r in records:
        code = r["code"]
        credit = r.get("credit") or {}
        sell = credit.get("sell")
        buy = credit.get("buy")
        ratio = credit.get("ratio")
        buy_oldest = credit.get("buy_oldest")

        if sell is not None and sell > 0 and (buy is not None):
            # 比率算出可能
            if ratio is None and sell:
                ratio = buy / sell
            category = "r"
            buy_change_pct = None
            if buy_oldest not in (None, 0) and buy is not None:
                buy_change_pct = (buy - buy_oldest) / buy_oldest * 100.0
            ratio_pairs.append((code, ratio))
            result[code] = {"category": category, "ratio": ratio, "buy_change_pct": buy_change_pct}
        elif buy is not None and buy > 0:
            # 売り残ゼロ（または実質ゼロ）の「買い長」
            category = "b"
            buy_change_pct = None
            if buy_oldest not in (None, 0):
                buy_change_pct = (buy - buy_oldest) / buy_oldest * 100.0
            result[code] = {"category": category, "ratio": None, "buy_change_pct": buy_change_pct}
        else:
            result[code] = {"category": "n", "ratio": None, "buy_change_pct": None}

    # 比率が算出できた銘柄同士でパーセンタイル順位（低いほど加点）
    ratio_scores = percentile_ranks(ratio_pairs, higher_is_better=False)

    for code, info in result.items():
        if info["category"] == "r":
            info["score"] = ratio_scores.get(code, 50.0)
        elif info["category"] == "b":
            pct = info["buy_change_pct"]
            if pct is None:
                info["score"] = config.BUY_ONLY_BASE
            else:
                raw = config.BUY_ONLY_BASE - pct * config.BUY_ONLY_TREND_COEF
                info["score"] = max(config.BUY_ONLY_MIN, min(config.BUY_ONLY_MAX, raw))
        else:
            info["score"] = 50.0
    return result


def compute_scores(records):
    """
    records: [{"code","name","market","price","streak","this_growth","avg_growth",
                "dev25","dev75","dev200","per","pbr","yield","credit":{...}}, ...]
    戻り値: 同じ辞書に "supply_score","supply_category","cred_ratio",
            "cred_buy_change_pct","score","rank" を追加したリスト（総合スコア降順）。
    """
    codes = [r["code"] for r in records]

    streak_scores = percentile_ranks([(r["code"], r.get("streak")) for r in records], True)
    this_growth_scores = percentile_ranks([(r["code"], r.get("this_growth")) for r in records], True)
    avg_growth_scores = percentile_ranks([(r["code"], r.get("avg_growth")) for r in records], True)

    dev25_scores = percentile_ranks([(r["code"], r.get("dev25")) for r in records], True)
    dev75_scores = percentile_ranks([(r["code"], r.get("dev75")) for r in records], True)
    dev200_scores = percentile_ranks([(r["code"], r.get("dev200")) for r in records], True)

    per_scores = percentile_ranks([(r["code"], r.get("per")) for r in records], False)

    supply = compute_supply_demand(records)

    out = []
    for r in records:
        code = r["code"]
        fundamental = (
            streak_scores[code] * config.W_STREAK
            + this_growth_scores[code] * config.W_THIS_GROWTH
            + avg_growth_scores[code] * config.W_AVG_GROWTH
        )
        technical = (
            dev25_scores[code] * config.W_DEV25
            + dev75_scores[code] * config.W_DEV75
            + dev200_scores[code] * config.W_DEV200
        )
        valuation = per_scores[code]
        supply_info = supply[code]

        total = (
            fundamental * config.WEIGHT_FUNDAMENTAL
            + technical * config.WEIGHT_TECHNICAL
            + valuation * config.WEIGHT_VALUATION
            + supply_info["score"] * config.WEIGHT_SUPPLY_DEMAND
        )

        row = dict(r)
        row["supply_score"] = round(supply_info["score"], 1)
        row["supply_category"] = supply_info["category"]
        row["cred_ratio"] = supply_info["ratio"]
        row["cred_buy_change_pct"] = supply_info["buy_change_pct"]
        row["score"] = round(total, 1)
        out.append(row)

    out.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(out, start=1):
        r["rank"] = i
    return out


def intersect_candidates(fundamental_rows, technical_rows):
    """コードで突合し、両方に含まれる銘柄だけを1つのレコードにマージする。"""
    tech_by_code = {r["code"]: r for r in technical_rows if r.get("code")}
    merged = []
    for f in fundamental_rows:
        code = f.get("code")
        if not code or code not in tech_by_code:
            continue
        t = tech_by_code[code]
        merged.append({
            "code": code,
            "name": f.get("name") or t.get("name"),
            "market": f.get("market") or t.get("market"),
            "price": f.get("price") if f.get("price") is not None else t.get("price"),
            "streak": f.get("streak"),
            "prev_growth": f.get("prev_growth"),
            "this_growth": f.get("this_growth"),
            "avg_growth": f.get("avg_growth"),
            "dev25": t.get("dev25"),
            "dev75": t.get("dev75"),
            "dev200": t.get("dev200"),
            "per": f.get("per") if f.get("per") is not None else t.get("per"),
            "pbr": t.get("pbr"),
            "yield": t.get("yield"),
        })
    return merged
