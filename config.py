# -*- coding: utf-8 -*-
"""
追跡したい株探ランキングページの一覧。
新しいページを追加したいときは、この辞書に1エントリ追加するだけでOK。

ranking_key : DB上の識別子（英数字、変更しない。変更すると別ランキング扱いになる）
category    : "銘柄探検" or "株価注意報" など分類用
title       : 表示名
url         : 取得先URL
"""

RANKINGS = {
    # --- 株価注意報：値動き系 ---
    "warning_trading_value_ranking": {
        "category": "株価注意報",
        "title": "本日の売買代金ランキング",
        "url": "https://kabutan.jp/warning/trading_value_ranking",
    },
    "warning_volume_ranking": {
        "category": "株価注意報",
        "title": "本日の出来高ランキング",
        "url": "https://kabutan.jp/warning/volume_ranking",
    },
    "warning_stop_high": {
        "category": "株価注意報",
        "title": "本日のストップ高銘柄",
        "url": "https://kabutan.jp/warning/?mode=3_1",
    },
    "warning_stop_low": {
        "category": "株価注意報",
        "title": "本日のストップ安銘柄",
        "url": "https://kabutan.jp/warning/?mode=3_2",
    },
    "warning_new_high": {
        "category": "株価注意報",
        "title": "本日、年初来高値を更新した銘柄",
        "url": "https://kabutan.jp/warning/?mode=3_3",
    },
    "warning_new_low": {
        "category": "株価注意報",
        "title": "本日、年初来安値を更新した銘柄",
        "url": "https://kabutan.jp/warning/?mode=3_4",
    },
    "warning_price_up": {
        "category": "株価注意報",
        "title": "今日の株価上昇率ランキング",
        "url": "https://kabutan.jp/warning/?mode=2_1",
    },
    "warning_price_down": {
        "category": "株価注意報",
        "title": "今日の株価下落率ランキング",
        "url": "https://kabutan.jp/warning/?mode=2_2",
    },

    # --- 株価注意報：需給系 ---
    "warning_margin_buy_up": {
        "category": "株価注意報",
        "title": "信用買い残の増加ランキング",
        "url": "https://kabutan.jp/warning/?mode=7_2",
    },
    "warning_margin_sell_up": {
        "category": "株価注意報",
        "title": "信用売り残の増加ランキング",
        "url": "https://kabutan.jp/warning/?mode=7_1",
    },
    "warning_margin_sell_down": {
        "category": "株価注意報",
        "title": "信用売り残の減少ランキング",
        "url": "https://kabutan.jp/warning/?mode=7_3",
    },
    "warning_margin_buy_down": {
        "category": "株価注意報",
        "title": "信用買い残の減少ランキング",
        "url": "https://kabutan.jp/warning/?mode=7_4",
    },
    "warning_margin_due_high": {
        "category": "株価注意報",
        "title": "信用【高値】期日到来銘柄",
        "url": "https://kabutan.jp/warning/?mode=7_5",
    },
    "warning_margin_due_low": {
        "category": "株価注意報",
        "title": "信用【安値】期日到来銘柄",
        "url": "https://kabutan.jp/warning/?mode=7_6",
    },
    "warning_golden_cross": {
        "category": "株価注意報",
        "title": "本日のゴールデンクロス銘柄（5日と25日移動平均線）",
        "url": "https://kabutan.jp/warning/?mode=6_1",
    },
    "warning_dead_cross": {
        "category": "株価注意報",
        "title": "本日のデッドクロス銘柄（5日と25日移動平均線）",
        "url": "https://kabutan.jp/warning/?mode=6_2",
    },
    "warning_above_ma25": {
        "category": "株価注意報",
        "title": "本日、株価が25日移動平均線を上抜いた銘柄",
        "url": "https://kabutan.jp/warning/?mode=6_3",
    },
    "warning_below_ma25": {
        "category": "株価注意報",
        "title": "本日、株価が25日移動平均線を下抜いた銘柄",
        "url": "https://kabutan.jp/warning/?mode=6_4",
    },
    "warning_nikkei_contribution": {
        "category": "株価注意報",
        "title": "日経平均の寄与度ランキング",
        "url": "https://kabutan.jp/warning/?mode=8_1",
    },

    # --- 銘柄探検：デイトレ向き ---
    "tansaku_volume_up": {
        "category": "銘柄探検",
        "title": "出来高急増銘柄",
        # {page} を差し込んで複数ページ取得する。max_pagesを指定しない場合は1ページ（{page}は無視）。
        "url": "https://kabutan.jp/tansaku/?mode=2_0311&market=0&capitalization=-1&dispmode=normal&stc=v3&stm=1&page={page}",
        "max_pages": 3,  # 1ページ50件 x 3 = 上位150件
    },

    # --- 銘柄探検：テクニカル（トレンド系・順張り） ---
    "tansaku_ichimoku_bull": {
        "category": "銘柄探検",
        "title": "一目均衡表「3役好転」",
        "url": "https://kabutan.jp/tansaku/?mode=2_0427",
    },
    "tansaku_ichimoku_bear": {
        "category": "銘柄探検",
        "title": "一目均衡表「3役逆転」",
        "url": "https://kabutan.jp/tansaku/?mode=2_0428",
    },
    "tansaku_parabolic_bull": {
        "category": "銘柄探検",
        "title": "パラボリック陽転",
        "url": "https://kabutan.jp/tansaku/?mode=2_0476",
    },
    "tansaku_parabolic_bear": {
        "category": "銘柄探検",
        "title": "パラボリック陰転",
        "url": "https://kabutan.jp/tansaku/?mode=2_0478",
    },
    "tansaku_shinne_bull": {
        "category": "銘柄探検",
        "title": "新値3本足陽転",
        "url": "https://kabutan.jp/tansaku/?mode=2_0490",
    },
    "tansaku_shinne_bear": {
        "category": "銘柄探検",
        "title": "新値3本足陰転",
        "url": "https://kabutan.jp/tansaku/?mode=2_0493",
    },

    # --- 銘柄探検：テクニカル（オシレーター系・逆張り） ---
    "tansaku_rsi_low": {
        "category": "銘柄探検",
        "title": "RSI（14日線）20%以下",
        "url": "https://kabutan.jp/tansaku/?mode=2_0460",
    },
    "tansaku_rsi_high": {
        "category": "銘柄探検",
        "title": "RSI（14日線）80%以上",
        "url": "https://kabutan.jp/tansaku/?mode=2_0462",
    },
    "tansaku_macd_buy": {
        "category": "銘柄探検",
        "title": "MACD／買いシグナル",
        "url": "https://kabutan.jp/tansaku/?mode=2_0440",
    },
    "tansaku_macd_sell": {
        "category": "銘柄探検",
        "title": "MACD／売りシグナル",
        "url": "https://kabutan.jp/tansaku/?mode=2_0445",
    },
}
