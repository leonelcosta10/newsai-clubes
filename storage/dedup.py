"""Registo simples de artigos/mensagens já processados, para evitar duplicados entre execuções."""

import sqlite3
from contextlib import contextmanager

from config import DEDUP_DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_items (
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    club TEXT,
    title TEXT,
    url TEXT,
    seen_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (source, external_id)
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DEDUP_DB_PATH)
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def is_seen(source: str, external_id: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM seen_items WHERE source = ? AND external_id = ?",
            (source, external_id),
        ).fetchone()
        return row is not None


def mark_seen(source: str, external_id: str, club: str = None, title: str = None, url: str = None) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO seen_items (source, external_id, club, title, url)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, external_id, club, title, url),
        )
