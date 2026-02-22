"""SQLite database initialization and connection management."""

import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.expanduser("~"), ".airbnb_tracker.db")


def get_connection(db_path=None):
    """Return a connection to the SQLite database."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            guest_name TEXT,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            nightly_rate REAL NOT NULL,
            nights INTEGER NOT NULL,
            total_revenue REAL NOT NULL,
            platform_fee REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (property_id) REFERENCES properties(id)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (property_id) REFERENCES properties(id)
        );
    """)
    conn.commit()
