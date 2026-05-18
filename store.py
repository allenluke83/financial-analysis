"""
store.py — SQLite database setup and helper functions.
 
All other modules import from here. Run this file directly to initialise
the database:
    python store.py
 
Tables
------
transactions  — every debit/credit from Monzo and Amex (stores actual transaction data)
balances      — point-in-time balance snapshots (Nationwide, Plum, T212, Monzo)
"""

import sqlite3
import os

# Creating path so database is vreated in same folder as store.py
DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")

# ------------------------
# Creating database schema - will contain one for all transactions and one for balances
# ------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ext_id      TEXT    NOT NULL,               -- source's own transaction ID
    source      TEXT    NOT NULL,               -- 'monzo' | 'amex'
    date        TEXT    NOT NULL,               -- ISO-8601: YYYY-MM-DD
    amount      INTEGER NOT NULL,               -- pence; negative = debit, positive = credit
    description TEXT    NOT NULL,
    category    TEXT,                           -- populated by categorise.py
    is_transfer INTEGER NOT NULL DEFAULT 0,     -- 1 = exclude from spend analytics
    raw_json    TEXT,                           -- full source payload, useful for debugging
    UNIQUE (ext_id, source)
);
 
CREATE TABLE IF NOT EXISTS balances (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account     TEXT    NOT NULL,               -- 'monzo' | 'amex' | 'nationwide' | 'plum' | 't212'
    date        TEXT    NOT NULL,               -- ISO-8601: YYYY-MM-DD
    balance     INTEGER NOT NULL,               -- pence
    UNIQUE (account, date)
);
 
CREATE INDEX IF NOT EXISTS idx_transactions_date   ON transactions (date);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions (source);
CREATE INDEX IF NOT EXISTS idx_balances_account    ON balances (account);
"""
 
# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
 
def get_connection() -> sqlite3.Connection:
    """
    Return a connection to the database with row_factory set so rows behave
    like dicts (access columns by name, not index).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safer for concurrent reads on the Pi
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
 
def init_db() -> None:
    """Create tables and indexes if they don't already exist."""
    with get_connection() as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialised at {DB_PATH}")
 
 
if __name__ == "__main__":
    init_db()