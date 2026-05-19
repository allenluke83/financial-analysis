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
# Write helpers
# ---------------------------------------------------------------------------
 
def insert_transaction(conn: sqlite3.Connection, tx: dict) -> bool:
    """
    Insert a single transaction. Returns True if inserted, False if it already
    existed (duplicate ext_id + source is silently ignored).
 
    Expected keys in tx:
        ext_id, source, date, amount (pence), description,
        category (optional), is_transfer (optional), raw_json (optional)
    """
    sql = """
        INSERT OR IGNORE INTO transactions
            (ext_id, source, date, amount, description, category, is_transfer, raw_json)
        VALUES
            (:ext_id, :source, :date, :amount, :description,
             :category, :is_transfer, :raw_json)
    """
    tx.setdefault("category", None)
    tx.setdefault("is_transfer", 0)
    tx.setdefault("raw_json", None)
 
    cursor = conn.execute(sql, tx)
    return cursor.rowcount == 1
 
 
def upsert_balance(conn: sqlite3.Connection, account: str, date: str, balance_pence: int) -> None:
    """
    Insert or replace a balance snapshot. Safe to call repeatedly — the most
    recent call for a given (account, date) wins.
    """
    conn.execute(
        """
        INSERT INTO balances (account, date, balance)
        VALUES (?, ?, ?)
        ON CONFLICT (account, date) DO UPDATE SET balance = excluded.balance
        """,
        (account, date, balance_pence),
    )
 
# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
 
def get_transactions(
    conn: sqlite3.Connection,
    source: str = None,
    exclude_transfers: bool = True,
) -> list[sqlite3.Row]:
    """
    Fetch transactions, optionally filtered by source and with transfers excluded.
    Returns rows ordered by date descending.
    """
    clauses = []
    params: list = []
 
    if source:
        clauses.append("source = ?")
        params.append(source)
    if exclude_transfers:
        clauses.append("is_transfer = 0")
 
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM transactions {where} ORDER BY date DESC", params
    ).fetchall()
    return rows
 
 
def get_latest_balances(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """
    Return the most recent balance snapshot for every account.
    """
    return conn.execute(
        """
        SELECT account, date, balance
        FROM balances
        WHERE (account, date) IN (
            SELECT account, MAX(date) FROM balances GROUP BY account
        )
        ORDER BY account
        """
    ).fetchall()
 

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