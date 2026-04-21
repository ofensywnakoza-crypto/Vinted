"""Baza danych SQLite - wszystkie ogloszenia, sprzedaz, snapshoty statystyk."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT UNIQUE,
    nr INTEGER,
    title TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    size TEXT,
    color TEXT,
    cost REAL DEFAULT 0,
    list_price REAL,
    sold_price REAL,
    commission REAL,
    net_profit REAL,
    margin REAL,
    status TEXT DEFAULT 'Wystawiony',
    platform TEXT DEFAULT 'Vinted PL',
    channel TEXT,
    listed_date TEXT,
    sold_date TEXT,
    days_to_sell INTEGER,
    current_views INTEGER DEFAULT 0,
    current_likes INTEGER DEFAULT 0,
    last_synced TEXT,
    vinted_url TEXT,
    photo_url TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stats_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    snapshot_date TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    price REAL,
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_snapshot_listing_date
    ON stats_snapshots(listing_id, snapshot_date);

CREATE TABLE IF NOT EXISTS actions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER,
    action_type TEXT NOT NULL,
    reason TEXT,
    executed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS trend_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    query TEXT,
    result_json TEXT,
    fetched_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT,
    title TEXT,
    brand TEXT,
    price REAL,
    estimated_resell REAL,
    margin_pct REAL,
    url TEXT UNIQUE,
    image_url TEXT,
    fetched_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_listing(data: dict) -> int:
    fields = [
        "external_id", "nr", "title", "brand", "category", "size", "color",
        "cost", "list_price", "sold_price", "commission", "net_profit", "margin",
        "status", "platform", "channel", "listed_date", "sold_date",
        "days_to_sell", "current_views", "current_likes", "last_synced",
        "vinted_url", "photo_url", "notes",
    ]
    values = {k: data.get(k) for k in fields}

    with get_conn() as conn:
        existing = None
        if values.get("external_id"):
            existing = conn.execute(
                "SELECT id FROM listings WHERE external_id = ?",
                (values["external_id"],),
            ).fetchone()
        elif values.get("nr") is not None:
            existing = conn.execute(
                "SELECT id FROM listings WHERE nr = ?", (values["nr"],)
            ).fetchone()

        if existing:
            listing_id = existing["id"]
            set_clause = ", ".join(
                f"{k} = COALESCE(?, {k})" for k in fields
            )
            conn.execute(
                f"UPDATE listings SET {set_clause}, updated_at = datetime('now') "
                f"WHERE id = ?",
                [*[values[k] for k in fields], listing_id],
            )
            return listing_id

        placeholders = ", ".join("?" for _ in fields)
        cur = conn.execute(
            f"INSERT INTO listings ({', '.join(fields)}) VALUES ({placeholders})",
            [values[k] for k in fields],
        )
        return cur.lastrowid


def save_snapshot(listing_id: int, views: int, likes: int, price: Optional[float] = None) -> None:
    today = date.today().isoformat()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM stats_snapshots WHERE listing_id = ? AND snapshot_date = ?",
            (listing_id, today),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE stats_snapshots SET views = ?, likes = ?, price = ? WHERE id = ?",
                (views, likes, price, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO stats_snapshots (listing_id, snapshot_date, views, likes, price) "
                "VALUES (?, ?, ?, ?, ?)",
                (listing_id, today, views, likes, price),
            )
        conn.execute(
            "UPDATE listings SET current_views = ?, current_likes = ?, "
            "last_synced = datetime('now') WHERE id = ?",
            (views, likes, listing_id),
        )


def get_all_listings(status: Optional[str] = None):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM listings WHERE status = ? ORDER BY listed_date DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM listings ORDER BY listed_date DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def get_active_listings():
    return get_all_listings(status="Wystawiony")


def get_listing(listing_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM listings WHERE id = ?", (listing_id,)
        ).fetchone()
        return dict(row) if row else None


def get_snapshots(listing_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM stats_snapshots WHERE listing_id = ? "
            "ORDER BY snapshot_date",
            (listing_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def log_action(listing_id: Optional[int], action_type: str, reason: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO actions_log (listing_id, action_type, reason) VALUES (?, ?, ?)",
            (listing_id, action_type, reason),
        )


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_sales_in_month(year: int, month: int) -> list[dict]:
    month_prefix = f"{year:04d}-{month:02d}"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE status = 'Sprzedany' "
            "AND sold_date LIKE ? ORDER BY sold_date",
            (f"{month_prefix}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_sales_on_date(target_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM listings WHERE status = 'Sprzedany' AND sold_date = ?",
            (target_date,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_all_listings() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM listings")
        conn.execute("DELETE FROM stats_snapshots")


def save_deal(deal: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deals "
            "(source, title, brand, price, estimated_resell, margin_pct, url, image_url, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                deal.get("source"),
                deal.get("title"),
                deal.get("brand"),
                deal.get("price"),
                deal.get("estimated_resell"),
                deal.get("margin_pct"),
                deal.get("url"),
                deal.get("image_url"),
            ),
        )


def get_recent_deals(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM deals ORDER BY margin_pct DESC, fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"Baza danych utworzona: {DB_PATH}")
