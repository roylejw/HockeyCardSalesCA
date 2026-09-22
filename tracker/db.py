import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "prices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY,
    store TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    product_key TEXT NOT NULL,
    image TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    ts TEXT NOT NULL,
    price REAL NOT NULL,
    regular REAL,
    in_stock INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS prices_listing_ts ON prices(listing_id, ts);
CREATE TABLE IF NOT EXISTS runs (
    ts TEXT NOT NULL,
    store TEXT NOT NULL,
    ok INTEGER NOT NULL,
    listings INTEGER NOT NULL,
    error TEXT
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_listing(conn, store, item, product_key, ts):
    conn.execute(
        """INSERT INTO listings (store, url, title, product_key, image, first_seen, last_seen)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(url) DO UPDATE SET title=excluded.title, product_key=excluded.product_key,
               image=COALESCE(excluded.image, listings.image), last_seen=excluded.last_seen""",
        (store, item["url"], item["title"], product_key, item.get("image"), ts, ts),
    )
    return conn.execute("SELECT id FROM listings WHERE url = ?", (item["url"],)).fetchone()["id"]


def record_price(conn, listing_id, item, ts):
    conn.execute(
        "INSERT INTO prices (listing_id, ts, price, regular, in_stock) VALUES (?, ?, ?, ?, ?)",
        (listing_id, ts, item["price"], item["regular"], int(item["in_stock"])),
    )
