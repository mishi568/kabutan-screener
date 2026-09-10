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

# ★★★ 未確認・要確認 ★★★
# 出来高急増ウォッチ（volume_watch.py）が使う「出来高ランキング」ページのURL。
# このURLはブラウザでkabutan.jpにアクセスして確認したものではなく、暫定的な
# 推測値です。実行して0件エラーになる、またはページの内容が明らかにおかしい
# 場合は、ブラウザでkabutan.jpのトップページなどから「ランキング」→
# 「出来高」を辿って実際のURLを確認し、下の値を書き換えてください。
VOLUME_RANKING_URL = "https://kabutan.jp/warning/?mode=2_1"

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

# --- 出来高急増ウォッチ専用設定（長期候補スクリーナーとは完全に別のDB・レポート） ---
VOLUME_DB_PATH = os.path.join(DATA_DIR, "volume_watch.db")
MAX_VOLUME_RANKING_PAGES = 40    # 出来高ランキングを何ページまで蓄積するか（1ページ50件想定）
# 「直近何営業日」を1つの検知ウィンドウとするか。カレンダー日ではなく、
# 「このツールを実際に実行した日」を新しい順に数えるため、土日祝日をまたいでも
# 毎営業日実行していれば自動的につじつまが合う。
VOLUME_LOOKBACK_RUNS = 5
# 出来高が「急増した」とみなす倍率（ウィンドウ内の最古日→最新日で何倍になったか）
VOLUME_SURGE_RATIO = 2.0
# 株価が「横ばい」とみなす変化率の上限（±この%以内なら横ばい扱い）
VOLUME_PRICE_FLAT_PCT = 3.0

# --- 信用取引（需給）データのキャッシュ ---
# kabutanの信用残は週次更新のため、候補銘柄180件超を毎回スクレイピングし直すのは
# 無駄が大きい。fetched_atからこの日数以内ならキャッシュ(data/screener.db内)を使い
# 再取得をスキップする。0にすると毎回必ず再取得する。
CREDIT_CACHE_MAX_AGE_DAYS = 6

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
