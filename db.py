# -*- coding: utf-8 -*-
"""
SQLiteデータベースの初期化・書き込みを担当するモジュール。
"""

import sqlite3

DB_PATH = "kabutan.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS rankings (
    ranking_key TEXT PRIMARY KEY,
    category    TEXT,
    title       TEXT,
    url         TEXT
);

CREATE TABLE IF NOT EXISTS stocks (
    code      TEXT PRIMARY KEY,
    name      TEXT,
    market    TEXT,
    last_seen DATE
);

CREATE TABLE IF NOT EXISTS ranking_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ranking_key   TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    rank          INTEGER,
    code          TEXT NOT NULL,
    name          TEXT,
    market        TEXT,
    extra         TEXT,
    UNIQUE(ranking_key, snapshot_date, code)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_code ON ranking_snapshots(code);
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON ranking_snapshots(snapshot_date);

-- バックテスト用：個別銘柄の日足四本値ヒストリー
CREATE TABLE IF NOT EXISTS price_history (
    code       TEXT NOT NULL,
    date       DATE NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    change     REAL,
    change_pct REAL,
    volume     INTEGER,
    PRIMARY KEY (code, date)
);

CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(date);

-- バックテスト用：ファネル抽出の結果そのものを日次で記録する
CREATE TABLE IF NOT EXISTS screening_picks (
    pick_date  DATE NOT NULL,
    funnel_key TEXT NOT NULL,   -- 例: "margin_x_technical_cross"
    code       TEXT NOT NULL,
    score      REAL,           -- スコア方式のファネルのみ使用。それ以外はNULL
    PRIMARY KEY (pick_date, funnel_key, code)
);

-- price_historyの取得進捗（銘柄ごとに「何ページ目まで取得済みか」を記録し、
-- 次回はそこから続きを取る。これがないと「浅く取った後に深く取り直す」ときに
-- 正しく差分取得できない）
CREATE TABLE IF NOT EXISTS price_history_progress (
    code           TEXT PRIMARY KEY,
    max_page_fetched INTEGER NOT NULL DEFAULT 0,
    reached_end    INTEGER NOT NULL DEFAULT 0  -- 1なら「これ以上過去のページは存在しない」ことを確認済み
);

-- 個別銘柄の詳細情報（PER/PBR/信用倍率/業績推移/信用取引週次など）をJSONでまるごと保存
CREATE TABLE IF NOT EXISTS stock_details (
    code          TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    data_json     TEXT,
    PRIMARY KEY (code, snapshot_date)
);

-- 保有銘柄（ポートフォリオ）の登録簿。screening_picks等の候補選定とは別枠で管理する。
-- 削除はせずremoved_dateを立てるだけ（売却後も履歴として残す）。
CREATE TABLE IF NOT EXISTS holdings (
    code         TEXT PRIMARY KEY,
    name         TEXT,
    memo         TEXT,
    added_date   DATE NOT NULL,
    removed_date DATE
);

-- 保有銘柄専用の株価ヒストリー。price_history（スクリーニング候補の深いバックフィル用、
-- 進捗管理ありで最新ページを取り直さない仕組み）とは切り離し、保有銘柄は
-- fetch_holdings_price.py が毎回「直近ページを取り直す」方式で常に最新化する。
CREATE TABLE IF NOT EXISTS holdings_price_history (
    code       TEXT NOT NULL,
    date       DATE NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL,
    change     REAL,
    change_pct REAL,
    volume     INTEGER,
    PRIMARY KEY (code, date)
);

CREATE INDEX IF NOT EXISTS idx_holdings_price_date ON holdings_price_history(date);

-- ============================================================
-- マクロ・需給データ（株探以外のデータ源: JPX公式・EDINET・nikkei225jp.com）
-- ============================================================

-- JPX公式: 空売り集計（全体）
CREATE TABLE IF NOT EXISTS jpx_short_selling (
    date TEXT PRIMARY KEY,
    short_selling_ratio REAL,
    short_selling_value REAL,
    total_value REAL,
    regulated_ratio REAL,
    non_regulated_ratio REAL,
    timestamp TEXT
);

-- JPX公式: 空売り集計（33業種別）
CREATE TABLE IF NOT EXISTS jpx_short_selling_sectors (
    date TEXT NOT NULL,
    sector TEXT NOT NULL,
    short_ratio REAL,
    PRIMARY KEY (date, sector)
);

-- JPX公式: 投資部門別売買動向
CREATE TABLE IF NOT EXISTS jpx_investor_trends (
    date TEXT PRIMARY KEY,
    foreign_net REAL,
    individual_net REAL,
    trust_bank_net REAL,
    investment_trust_net REAL,
    business_corp_net REAL,
    other_net REAL,
    timestamp TEXT
);

-- JPX公式: 銘柄別信用取引残高（週次）
CREATE TABLE IF NOT EXISTS jpx_margin_positions (
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    margin_buy REAL,
    margin_sell REAL,
    margin_ratio REAL,
    margin_buy_change REAL,
    margin_sell_change REAL,
    timestamp TEXT,
    PRIMARY KEY (date, code)
);

-- JPX公式: 機関投資家の個別銘柄空売りポジション（0.5%以上の開示義務分）
CREATE TABLE IF NOT EXISTS jpx_short_positions (
    date TEXT NOT NULL,
    code TEXT NOT NULL,
    holder_name TEXT NOT NULL,
    short_position_ratio REAL,
    short_position_shares REAL,
    disclosure_date TEXT,
    timestamp TEXT,
    PRIMARY KEY (date, code, holder_name)
);

-- EDINET: 大量保有報告書（5%以上）
CREATE TABLE IF NOT EXISTS edinet_large_holdings (
    doc_id TEXT PRIMARY KEY,
    date TEXT,
    code TEXT,
    issuer_name TEXT,
    holder_name TEXT,
    holding_ratio REAL,
    report_type TEXT,
    purpose TEXT,
    submission_date TEXT,
    timestamp TEXT
);

-- nikkei225jp.com: 日本225 PER/PBR
CREATE TABLE IF NOT EXISTS nikkei_per_records (
    date TEXT PRIMARY KEY,
    price REAL,
    per REAL,
    pbr REAL,
    eps REAL,
    bps REAL,
    earnings_yield REAL,
    dividend_yield REAL,
    jgb_yield REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 騰落レシオ
CREATE TABLE IF NOT EXISTS nikkei_touraku_records (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change REAL,
    prime_volume REAL,
    advancing_count REAL,
    declining_count REAL,
    touraku_6d REAL,
    touraku_10d REAL,
    touraku_15d REAL,
    touraku_25d REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 信用残高（日本市況、sinyou.php）
CREATE TABLE IF NOT EXISTS nikkei_margin_records (
    date TEXT PRIMARY KEY,
    margin_buy REAL,
    margin_sell REAL,
    margin_buy_shares REAL,
    margin_sell_shares REAL,
    margin_buy_change_pct REAL,
    margin_sell_change_pct REAL,
    margin_ratio REAL,
    profit_loss_ratio REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 投資主体別売買状況（週次、JPX投資部門別動向の補完・裏取り用）
CREATE TABLE IF NOT EXISTS nikkei225jp_investor_trends (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change_pct REAL,
    foreign_net REAL,
    dealer_net REAL,
    individual_net REAL,
    individual_cash_net REAL,
    individual_margin_net REAL,
    investment_trust_net REAL,
    business_corp_net REAL,
    other_corp_net REAL,
    trust_bank_net REAL,
    insurance_net REAL,
    bank_net REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 空売り比率（JPX空売り集計の補完・裏取り用）
CREATE TABLE IF NOT EXISTS nikkei225jp_short_selling (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change REAL,
    prime_trading_value REAL,
    prime_volume REAL,
    short_ratio_total REAL,
    short_ratio_regulated REAL,
    short_ratio_non_regulated REAL,
    timestamp TEXT
);

-- nikkei225jp.com: NT倍率（日経平均/TOPIX）
CREATE TABLE IF NOT EXISTS nikkei225jp_nt_ratio (
    date TEXT PRIMARY KEY,
    nt_ratio REAL,
    nj_ratio REAL,
    jt_ratio REAL,
    nikkei_price REAL,
    nikkei_change_pct REAL,
    topix_price REAL,
    topix_change_pct REAL,
    jpx400_price REAL,
    jpx400_change_pct REAL,
    usdjpy REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 裁定買い残/売り残（日次・株数ベース）
CREATE TABLE IF NOT EXISTS nikkei225jp_arbitrage (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change REAL,
    prime_trading_value REAL,
    buy_shares REAL,
    sell_shares REAL,
    net_shares REAL,
    net_change REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 週次建玉数手口（日経225先物、証券会社カテゴリ別）
CREATE TABLE IF NOT EXISTS nikkei225jp_futures_broker (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change REAL,
    foreign_buy REAL,
    foreign_sell REAL,
    foreign_net REAL,
    foreign_net_change REAL,
    domestic_buy REAL,
    domestic_sell REAL,
    domestic_net REAL,
    domestic_net_change REAL,
    retail_buy REAL,
    retail_sell REAL,
    retail_net REAL,
    retail_net_change REAL,
    timestamp TEXT
);

-- nikkei225jp.com: 恐怖指数（日本VI・VSTOXX・VIX）
CREATE TABLE IF NOT EXISTS nikkei225jp_fear_index (
    date TEXT PRIMARY KEY,
    price REAL,
    price_change REAL,
    prime_volume REAL,
    japan_vi REAL,
    vstoxx REAL,
    vix REAL,
    timestamp TEXT
);
"""


def get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """CREATE TABLE IF NOT EXISTSでは既存テーブルに新しい列は追加されないため、
    後から足した列はここで個別にマイグレーションする。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(screening_picks)").fetchall()}
    if "score" not in cols:
        conn.execute("ALTER TABLE screening_picks ADD COLUMN score REAL")
        conn.commit()


def upsert_ranking_def(conn, ranking_key, category, title, url):
    conn.execute(
        """
        INSERT INTO rankings(ranking_key, category, title, url)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(ranking_key) DO UPDATE SET
            category = excluded.category,
            title    = excluded.title,
            url      = excluded.url
        """,
        (ranking_key, category, title, url),
    )


def upsert_stock(conn, code, name, market, seen_date):
    conn.execute(
        """
        INSERT INTO stocks(code, name, market, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name      = excluded.name,
            market    = excluded.market,
            last_seen = excluded.last_seen
        """,
        (code, name, market, seen_date),
    )


def get_stock_name(conn, code: str) -> str | None:
    row = conn.execute("SELECT name FROM stocks WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def get_latest_edinet_date(conn) -> str | None:
    row = conn.execute("SELECT MAX(date) FROM edinet_large_holdings").fetchone()
    return row[0] if row else None


def save_sector_short_ratios(conn, date: str, sector_ratios: dict[str, float]):
    """JPX空売り集計PDFの33業種別空売り比率を保存する(jpx_short_selling_sectors、date×sector単位)。"""
    conn.executemany(
        """
        INSERT INTO jpx_short_selling_sectors (date, sector, short_ratio)
        VALUES (?, ?, ?)
        ON CONFLICT(date, sector) DO UPDATE SET short_ratio = excluded.short_ratio
        """,
        [(date, sector, ratio) for sector, ratio in sector_ratios.items()],
    )


def insert_snapshot_records(conn, records: list[dict]):
    conn.executemany(
        """
        INSERT OR IGNORE INTO ranking_snapshots
            (ranking_key, snapshot_date, rank, code, name, market, extra)
        VALUES
            (:ranking_key, :snapshot_date, :rank, :code, :name, :market, :extra)
        """,
        records,
    )


def get_all_codes(conn) -> list[str]:
    """stocksテーブルに登録済みの全銘柄コードを返す（＝これまでにランキングへ出現した銘柄）"""
    rows = conn.execute("SELECT code FROM stocks ORDER BY code").fetchall()
    return [r[0] for r in rows]


def get_known_dates(conn, code: str) -> set[str]:
    """指定銘柄について、price_historyに既に保存済みの日付集合を返す（差分更新の判定用）"""
    rows = conn.execute("SELECT date FROM price_history WHERE code = ?", (code,)).fetchall()
    return {r[0] for r in rows}


def insert_price_history(conn, records: list[dict]):
    conn.executemany(
        """
        INSERT OR IGNORE INTO price_history
            (code, date, open, high, low, close, change, change_pct, volume)
        VALUES
            (:code, :date, :open, :high, :low, :close, :change, :change_pct, :volume)
        """,
        records,
    )


def insert_screening_picks(conn, pick_date: str, funnel_key: str, codes: list[str], scores: dict | None = None):
    """指定した (pick_date, funnel_key) の行をいったん全部消してから入れ直す（洗い替え）。
    再実行のたびに古い候補が残り続けるのを防ぐため。"""
    conn.execute(
        "DELETE FROM screening_picks WHERE pick_date = ? AND funnel_key = ?",
        (pick_date, funnel_key),
    )
    conn.executemany(
        "INSERT INTO screening_picks (pick_date, funnel_key, code, score) VALUES (?, ?, ?, ?)",
        [(pick_date, funnel_key, code, (scores or {}).get(code)) for code in codes],
    )
    conn.commit()


def insert_stock_detail(conn, code: str, snapshot_date: str, data_json: str):
    conn.execute(
        """
        INSERT INTO stock_details (code, snapshot_date, data_json)
        VALUES (?, ?, ?)
        ON CONFLICT(code, snapshot_date) DO UPDATE SET data_json = excluded.data_json
        """,
        (code, snapshot_date, data_json),
    )
    conn.commit()


def upsert_record(conn, table: str, key_columns: tuple[str, ...], record: dict):
    """dictのキーをそのまま列名として使い、INSERT ... ON CONFLICT DO UPDATEを組み立てる。
    JPX/EDINET/nikkei225jp.com系の新規テーブル(13種)はいずれも列構成が異なるため、
    テーブルごとに個別の upsert_xxx() 関数を書く代わりにこの汎用関数を共有する。
    """
    columns = list(record.keys())
    column_list = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in key_columns)
    key_list = ", ".join(key_columns)
    sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"
    if update_clause:
        sql += f" ON CONFLICT({key_list}) DO UPDATE SET {update_clause}"
    conn.execute(sql, record)


def get_progress(conn, code: str) -> tuple[int, bool]:
    """(これまでに取得済みの最深ページ番号, 履歴の終端に到達済みか)を返す。未取得なら(0, False)。"""
    row = conn.execute(
        "SELECT max_page_fetched, reached_end FROM price_history_progress WHERE code = ?", (code,)
    ).fetchone()
    if row is None:
        return 0, False
    return row[0], bool(row[1])


def set_progress(conn, code: str, max_page_fetched: int, reached_end: bool):
    conn.execute(
        """
        INSERT INTO price_history_progress (code, max_page_fetched, reached_end)
        VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            max_page_fetched = MAX(price_history_progress.max_page_fetched, excluded.max_page_fetched),
            reached_end      = MAX(price_history_progress.reached_end, excluded.reached_end)
        """,
        (code, max_page_fetched, int(reached_end)),
    )


def add_holding(conn, code: str, added_date: str, name: str | None = None, memo: str | None = None):
    """保有銘柄を登録する（既に登録済み・解除済みの場合は再度保有中に戻す）。"""
    conn.execute(
        """
        INSERT INTO holdings (code, name, memo, added_date, removed_date)
        VALUES (?, ?, ?, ?, NULL)
        ON CONFLICT(code) DO UPDATE SET
            name         = COALESCE(excluded.name, holdings.name),
            memo         = COALESCE(excluded.memo, holdings.memo),
            added_date   = excluded.added_date,
            removed_date = NULL
        """,
        (code, name, memo, added_date),
    )
    conn.commit()


def remove_holding(conn, code: str, removed_date: str):
    """保有銘柄を解除する（行は削除せず、removed_dateを立てて履歴として残す）。"""
    conn.execute("UPDATE holdings SET removed_date = ? WHERE code = ?", (removed_date, code))
    conn.commit()


def get_active_holdings(conn) -> list[str]:
    """現在保有中（removed_dateが未設定）の銘柄コード一覧を返す。"""
    rows = conn.execute(
        "SELECT code FROM holdings WHERE removed_date IS NULL ORDER BY code"
    ).fetchall()
    return [r[0] for r in rows]


def get_all_holdings(conn) -> list[tuple]:
    """保有中・解除済み含む全登録銘柄を返す（(code, name, memo, added_date, removed_date)のタプル）。"""
    return conn.execute(
        "SELECT code, name, memo, added_date, removed_date FROM holdings ORDER BY removed_date IS NOT NULL, added_date DESC"
    ).fetchall()


def insert_holdings_price(conn, records: list[dict]):
    conn.executemany(
        """
        INSERT OR IGNORE INTO holdings_price_history
            (code, date, open, high, low, close, change, change_pct, volume)
        VALUES
            (:code, :date, :open, :high, :low, :close, :change, :change_pct, :volume)
        """,
        records,
    )
