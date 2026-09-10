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
