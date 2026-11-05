"""Database setup for the Order Service."""

import os
import sqlite3
from pathlib import Path
from contextlib import closing


DB_PATH = Path(
    os.environ.get(
        "ORDER_DB_PATH",
        str(Path(__file__).resolve().parent / "orders.db")
    )
)


def get_connection():
    """Create and return a database connection."""
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Initialize the orders database without deleting existing orders."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(get_connection()) as connection:

        connection.execute("PRAGMA journal_mode=WAL")

        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity = 1),
                    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                    created_at TEXT NOT NULL
                )
            """)


if __name__ == "__main__":
    init_db()
    print("Order database initialized successfully.")
