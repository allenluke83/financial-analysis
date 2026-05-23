#%%
import os
import json
import sqlite3
import requests
from dotenv import load_dotenv

DB_PATH = "finance.db"
ENV_PATH = ".env"
#%%
def refresh_monzo_tokens():
    """Uses the permanent refresh token to get a new access token and saves it."""
    load_dotenv(ENV_PATH)
    
    client_id = os.getenv("MONZO_CLIENT_ID")
    client_secret = os.getenv("MONZO_CLIENT_SECRET")
    refresh_token = os.getenv("MONZO_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing OAuth credentials in .env file. Ensure your client keys and refresh token are set.")
        
    print("Refreshing Monzo tokens...")
    url = "https://api.monzo.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }
    
    response = requests.post(url, data=data)
    if response.status_code != 200:
        raise Exception(f"Failed to refresh token: {response.status_code} - {response.text}")
        
    tokens = response.json()
    new_access_token = tokens["access_token"]
    new_refresh_token = tokens["refresh_token"]
    
    # Update the .env file dynamically so the next run uses the fresh tokens
    with open(ENV_PATH, "r") as f:
        lines = f.readlines()
        
    with open(ENV_PATH, "w") as f:
        for line in lines:
            if line.startswith("MONZO_ACCESS_TOKEN="):
                f.write(f'MONZO_ACCESS_TOKEN="{new_access_token}"\n')
            elif line.startswith("MONZO_REFRESH_TOKEN="):
                f.write(f'MONZO_REFRESH_TOKEN="{new_refresh_token}"\n')
            else:
                f.write(line)
                
    # Force reload environment variables for the current execution context
    os.environ["MONZO_ACCESS_TOKEN"] = new_access_token
    os.environ["MONZO_REFRESH_TOKEN"] = new_refresh_token
    print("Tokens refreshed and saved successfully.")


def get_latest_monzo_ext_id():
    """Finds the most recent Monzo external ID in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ext_id FROM transactions WHERE source = 'monzo' ORDER BY date DESC, id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        refresh_monzo_tokens()

    except Exception as e:
            print(f"Failed to sync Monzo data: {e}")


def fetch_monzo_transactions(since_id=None):
    """Fetches transactions from the Monzo API."""
    access_token = os.getenv("MONZO_ACCESS_TOKEN")
    account_id = os.getenv("MONZO_ACCOUNT_ID")
    
    url = "https://api.monzo.com/transactions"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "account_id": account_id,
        "expand[]": "merchant"  # Pulls full merchant metadata details
    }
    
    if since_id:
        params["since"] = since_id

    print("Fetching Monzo transactions...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Monzo API Error: {response.status_code} - {response.text}")
        
    return response.json().get("transactions", [])


def save_transactions_to_db(transactions):
    """Parses Monzo transactions and inserts them into the transactions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted_count = 0
    
    for tx in transactions:
        # Avoid recording declined or incomplete transactions
        if tx.get("decline_reason"):
            continue
            
        ext_id = tx["id"]
        date_str = tx["created"][:10]  # Extracts YYYY-MM-DD
        
        # Determine the cleanest name for description
        description = tx.get("description")
        if tx.get("merchant") and tx["merchant"].get("name"):
            description = tx["merchant"]["name"]
            
        # Monzo stores internally in pence integers, directly mapping to schema!
        amount_pence = int(tx["amount"])
        
        # Early transfer flagger for Deduplication Logic
        is_transfer = 0
        desc_lower = description.lower() if description else ""
        if (
            tx.get("scheme") == "uk_retail_pots" or 
            "plum" in desc_lower or 
            "trading 212" in desc_lower or 
            "amex" in desc_lower or 
            "american express" in desc_lower or
            "nationwide" in desc_lower
        ):
            is_transfer = 1
            
        raw_json_str = json.dumps(tx)
        
        try:
            # Matches exact unique constraint structure: UNIQUE (ext_id, source)
            cursor.execute(
                """
                INSERT OR IGNORE INTO transactions (ext_id, source, date, amount, description, category, is_transfer, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ext_id, "monzo", date_str, amount_pence, description, None, is_transfer, raw_json_str)
            )
            if cursor.rowcount > 0:
                inserted_count += 1
        except sqlite3.Error as e:
            print(f"Database error inserting transaction {ext_id}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Successfully synced {inserted_count} new Monzo transactions.")
