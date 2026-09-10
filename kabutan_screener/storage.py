# -*- coding: utf-8 -*-
"""SQLiteへのデータ蓄積。実行のたびに runs テーブルへ1件、
成功時は stocks テーブルへその日のスナップショットを保存する。
過去分は消さずに溜めていくので、後で推移を振り返ることができる。"""

import os
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    ran_at TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT,
    stock_count INTEGER,
    top_code TEXT,
    top_name TEXT,
    top_score REAL
);

CREATE TABLE IF NOT EXISTS stocks (
    run_date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    market TEXT,
    price REAL,
    streak INTEGER,
    this_growth REAL,
    avg_growth REAL,
    dev25 REAL,
    dev75 REAL,
    dev200 REAL,
    per REAL,
    pbr REAL,
    yield REAL,
    cred_ratio REAL,
    cred_buy_change_pct REAL,
    supply_category TEXT,
    supply_score REAL,
    score REAL,
    rank INTEGER,
    PRIMARY KEY (run_date, code)
);
"""


@contextmanager
def connect():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_run(date, ran_at, status, summary, stock_count=None, top_code=None, top_name=None, top_score=None):
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (date, ran_at, status, summary, stock_count, top_code, top_name, top_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                ran_at=excluded.ran_at, status=excluded.status, summary=excluded.summary,
                stock_count=excluded.stock_count, top_code=excluded.top_code,
                top_name=excluded.top_name, top_score=excluded.top_score
            """,
            (date, ran_at, status, summary, stock_count, top_code, top_name, top_score),
        )


def save_stocks(date, records):
    with connect() as conn:
        conn.execute("DELETE FROM stocks WHERE run_date = ?", (date,))
        conn.executemany(
            """
            INSERT INTO stocks (
                run_date, code, name, market, price, streak, this_growth, avg_growth,
                dev25, dev75, dev200, per, pbr, yield, cred_ratio, cred_buy_change_pct,
                supply_category, supply_score, score, rank
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    date, r["code"], r.get("name"), r.get("market"), r.get("price"),
                    r.get("streak"), r.get("this_growth"), r.get("avg_growth"),
                    r.get("dev25"), r.get("dev75"), r.get("dev200"), r.get("per"),
                    r.get("pbr"), r.get("yield"), r.get("cred_ratio"), r.get("cred_buy_change_pct"),
                    r.get("supply_category"), r.get("supply_score"), r.get("score"), r.get("rank"),
                )
                for r in records
            ],
        )


def get_recent_runs(limit=14):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_success_date(before_date=None):
    with connect() as conn:
        if before_date:
            row = conn.execute(
                "SELECT date FROM runs WHERE status='success' AND date < ? ORDER BY date DESC LIMIT 1",
                (before_date,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT date FROM runs WHERE status='success' ORDER BY date DESC LIMIT 1"
            ).fetchone()
        return row["date"] if row else None


def get_stocks_for_run(date):
    if not date:
        return []
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM stocks WHERE run_date = ? ORDER BY rank ASC", (date,)
        ).fetchall()
        return [dict(r) for r in rows]
