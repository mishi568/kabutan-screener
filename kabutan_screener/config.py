# -*- coding: utf-8 -*-
"""設定値: URL、スコア計算の重み、ファイルパスなど。"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "screener.db")
RAW_HTML_DEBUG_DIR = os.path.join(DATA_DIR, "raw_pages")  # デバッグ用に生HTMLを保存する場所

# --- 対象URL ---
FUNDAMENTAL_RANKING_URL = "https://kabutan.jp/tansaku/consecutive_annual_operating_profit_growth_ranking"
TECHNICAL_RANKING_URL = "https://kabutan.jp/tansaku/?mode=2_0262"
STOCK_PAGE_URL = "https://kabutan.jp/stock/?code={code}"

# 対象とする市場（この文字列を含む市場表記のみ候補にする。ETF/REIT等は自然に除外される）
TARGET_MARKETS = ["プライム", "スタンダード", "グロース"]

# --- クロール設定 ---
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "kabutan-screener-personal-use/1.0"
)
REQUEST_TIMEOUT_SEC = 20
REQUEST_DELAY_SEC = 0.8          # ランキングページ間のウェイト
CREDIT_REQUEST_DELAY_SEC = 0.6   # 個別銘柄ページ取得間のウェイト
MAX_RANKING_PAGES = 40           # 安全装置（無限ループ防止。1ページ50件なので2000件相当）

# --- 連続増益の最低期数（候補条件） ---
MIN_PROFIT_GROWTH_STREAK = 3

# --- スコアリングの重み ---
WEIGHT_FUNDAMENTAL = 0.40
WEIGHT_TECHNICAL = 0.35
WEIGHT_VALUATION = 0.10
WEIGHT_SUPPLY_DEMAND = 0.15

# ファンダメンタルズ内訳
W_STREAK = 0.35
W_THIS_GROWTH = 0.40
W_AVG_GROWTH = 0.25

# テクニカル内訳（移動平均線カイリ率）
W_DEV25 = 0.25
W_DEV75 = 0.35
W_DEV200 = 0.40

# 需給スコア: 買い長銘柄の代替評価式で使う係数
BUY_ONLY_BASE = 50.0
BUY_ONLY_TREND_COEF = 0.5
BUY_ONLY_MIN = 15.0
BUY_ONLY_MAX = 65.0
