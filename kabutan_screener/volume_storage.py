# -*- coding: utf-8 -*-
"""
出来高急増ウォッチ専用のSQLite保存処理。

長期上昇候補スクリーナーとは完全に別のデータベースファイル
(data/volume_watch.db)を使う（storage.py / data/screener.db とは無関係）。
実行のたびに、その時点の出来高ランキング上位をまるごとスナップショットとして
蓄積していき、直近N回ぶんを比較することで「出来高急増・株価横ばい」銘柄を
検出できるようにする。
"""

import os
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS volume_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    ran_at TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    stock_count INTEGER
);

CREATE TABLE IF NOT EXISTS volume_ranking (
    run_date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    market TEXT,
    price REAL,
    volume REAL,
    change_pct REAL,
    rank INTEGER,
    PRIMARY KEY (run_date, code)
);
"""


@contextmanager
def connect():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.VOLUME_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_run(date, ran_at, status, summary, stock_count=None):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO volume_runs (date, ran_at, status, summary, stock_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                ran_at=excluded.ran_at, status=excluded.status,
                summary=excluded.summary, stock_count=excluded.stock_count
            """,
            (date, ran_at, status, summary, stock_count),
        )


def save_ranking(date, records):
    with connect() as conn:
        conn.execute("DELETE FROM volume_ranking WHERE run_date = ?", (date,))
        conn.executemany(
            """
            INSERT INTO volume_ranking (run_date, code, name, market, price, volume, change_pct, rank)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    date, r["code"], r.get("name"), r.get("market"),
                    r.get("price"), r.get("volume"), r.get("change_pct"), r.get("rank"),
                )
                for r in records
            ],
        )


def get_recent_runs(limit=14):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM volume_runs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_success_dates(limit):
    """直近の「成功した実行日」を新しい順にlimit件返す（カレンダー日ではなく実行回ベース）。"""
    with connect() as conn:
        rows = conn.execute(
            "SELECT date FROM volume_runs WHERE status='success' ORDER BY date DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r["date"] for r in rows]


def get_ranking_for_run(date):
    if not date:
        return []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM volume_ranking WHERE run_date = ? ORDER BY rank ASC", (date,)
        ).fetchall()
        return [dict(r) for r in rows]
