#%%
import os
import sqlite3
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "finance.db"

# ==========================================
# 1. PLATFORM FETCH FUNCTIONS
# ==========================================

class Trading212:

    def __init__(self):
        self.api_key = os.getenv("T212_API_KEY")
        self.api_secret = os.getenv("T212_API_SECRET")
        self.base_url = "https://live.trading212.com/api/v0"
        self.endpoint = "/equity/account/summary"

    # This function connects to api to get summary
    def get_data(self):
        url = f"{self.base_url}{self.endpoint}"
        response = requests.get(url, auth=(self.api_key, self.api_secret))
        if response.status_code == 200:
            return response.json()
        print(f"Error fetching {self.endpoint}: {response.status_code}")
        return None
    


def fetch_all_balances():
    """Gathers platform data and converts values to pence integers for the DB."""
    # Fetch live API data
    t212 = Trading212()
    t212_summary = t212.get_data()
    
    # Convert T212 float pounds to pence integer
    t212_bal = int(t212_summary["totalValue"] * 100) if t212_summary else 0
    # Fetch hardcoded data from .env and convert pounds (float/int) to pence integer
    monzo_bal = int(float(os.getenv("MONZO_INVESTMENT_BALANCE", 0.0)) * 100)
    plum_bal = int(float(os.getenv("PLUM_BALANCE", 0.0)) * 100)
    nationwide_bal = int(float(os.getenv("NATIONWIDE_BALANCES", 0.0)) * 100)

    # Dictionary keys map exactly to your schema columns: account, balance
    return [
        {"account": "t212", "balance": t212_bal},
        {"account": "monzo", "balance": monzo_bal},
        {"account": "plum", "balance": plum_bal},
        {"account": "nationwide", "balance": nationwide_bal}
    ]

# ==========================================
# 2. DATABASE 
# ==========================================

def save_balances_to_db(snapshots):

    if not snapshots:
        print("No balances data provided to save.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure the table is primed using exact schema definition
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS balances (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        account     TEXT    NOT NULL,               -- 'monzo' | 'amex' | 'nationwide' | 'plum' | 't212'
        date        TEXT    NOT NULL,               -- ISO-8601: YYYY-MM-DD
        balance     INTEGER NOT NULL,               -- pence
        UNIQUE (account, date)
    );
    """)

    # INSERT OR REPLACE handles UNIQUE(account, date) constraint
    query = """
    INSERT OR REPLACE INTO balances (account, date, balance)
    VALUES (:account, DATE('now'), :balance);
    """

    try:
        for snapshot in snapshots:
            cursor.execute(query, snapshot)
        conn.commit()
        print(f"Successfully logged {len(snapshots)} account balances.")
    except Exception as e:
        conn.rollback()
        print(f"Failed to write to database: {e}")
    finally:
        conn.close()

#%%

# ==========================================
# 3. ORCHESTRATION RUNNER
# ==========================================

def run_balance_pipeline():
    print("Starting daily account balance snapshot...")
    balances = fetch_all_balances()
    save_balances_to_db(balances)

if __name__ == "__main__":
    run_balance_pipeline()
# %%
