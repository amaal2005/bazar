"""SQLite storage and initial catalog data."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

# Docker can override this path to use a persistent volume.
DB_PATH = Path(
    os.environ.get(
        "CATALOG_DB_PATH",
        str(Path(__file__).resolve().parent / "catalog.db"),
    )
)

BOOKS = [
    (
        1,
        "How to get a good grade in DOS in 40 minutes a day.",
        "distributed systems",
        10,
        4000,
    ),
    (2, "RPCs for Noobs.", "distributed systems", 10, 5000),
    (
        3,
        "Xen and the Art of Surviving Undergraduate School.",
        "undergraduate school",
        10,
        6000,
    ),
    (
        4,
        "Cooking for the Impatient Undergrad.",
        "undergraduate school",
        10,
        3000,
    ),
]


def get_connection():
    """Open a connection with named columns and a lock timeout."""
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create storage and seed books without resetting existing data."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(get_connection()) as connection:
        connection.execute("PRAGMA journal_mode=WAL")

        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    price_cents INTEGER NOT NULL CHECK (price_cents >= 0)
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO books
                    (id, title, topic, quantity, price_cents)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                BOOKS,
            )


if __name__ == "__main__":
    init_db()
    print(f"Catalog database initialized: {DB_PATH}")
