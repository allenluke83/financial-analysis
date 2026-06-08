#%%
import os
import csv
import hashlib
import sqlite3
from datetime import datetime
import json
import glob

# Define the folder directory
folder_path = "./amex_statement"

DB_PATH = "finance.db"

def generate_amex_ext_id(date_str, description, amount_pence):
    """
    There isn't an ext_id for amex so will generate one here by combining cols
    """
    unique_string = f"{date_str}||{description}||{amount_pence}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()


def clean_amex_amount(amount_str):
    """
    Converts Amex string amounts to pence integers.
    Inverts the sign to match your schema logic
    """
    # Clean up formatting characters like currency symbols or quotes
    clean_str = amount_str.replace("£", "").replace(",", "").strip()
    
    # Convert to float first, then scale to copper pence
    amount_float = float(clean_str)
    amount_pence = int(round(amount_float * 100))
    
    # Invert sign to match your standard: spending must be negative!
    return amount_pence * -1

def clean_amex_date(date_str):
    """Converts Amex dates (DD/MM/YYYY) into ISO-8601 (YYYY-MM-DD)."""
    parsed_date = datetime.strptime(date_str.strip(), "%d/%m/%Y")
    return parsed_date.strftime("%Y-%m-%d")


def import_amex_csv(csv_file_path):
    if not os.path.exists(csv_file_path):
        print(f"Error: File not found at {csv_file_path}")
        return

    # conn = sqlite3.connect(DB_PATH)
    # cursor = conn.cursor()
    # inserted_count = 0

    print(f"Processing American Express statement: {csv_file_path}...")

    amex_dict = []

    with open(csv_file_path, mode="r", encoding="utf-8-sig") as f:
        # Use csv.reader to parse
        reader = csv.reader(f)
        count = 0
        
        for row in reader:
            # Skip empty lines
            if not row or len(row) < 3:
                continue
            
            # Defensive check: skip rows that do not start with a valid date format
            date_raw = row[0]
            if "/" not in date_raw:
                continue  # Skips row if it's a header label like "Date" instead of "19/05/2026"

            try:
                # 1. Standardise fields
                date_iso = clean_amex_date(date_raw)
                description = row[1].strip() if len(row) > 3 else row[1].strip()
                amount_pence = clean_amex_amount(row[2])
                
                # 2. Build our unique external identifier tracking key
                ext_id = generate_amex_ext_id(date_iso, description, amount_pence)
                
                # 3. Handle Transfer Logic (Amex payments received from your Monzo current account)
                is_transfer = 0
                desc_lower = description.lower()
                if "payment received" in desc_lower or "monzo" in desc_lower:
                    is_transfer = 1

                # 4. Raw category logic
                raw_category = row[10]

                count += 1

            except Exception as e:
                print(f"⚠️ Skipping malformed row {row}: {e}")
                continue

            # Append dict in same way as monzo

            amex_dict.append({"ext_id":ext_id,
                              "source":"amex",
                                "date":date_iso,
                                "amount":amount_pence,
                                "description":description,
                                "category":raw_category,
                                "is_transfer":is_transfer,
                                "raw_json":None})
            
    return amex_dict


def save_amex_to_db(transactions):
    """Parses Amex transactions and inserts them into the transactions table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    inserted_count = 0
    
    for tx in transactions:
        # Avoid recording declined or incomplete transactions
        ext_id = tx["ext_id"]
        date_str = tx["date"] # Extracts YYYY-MM-DD
        raw_category = tx["category"]
        
        # Determine the cleanest name for description
        description = tx.get("description")

        # Monzo stores internally in pence integers, directly mapping to schema!
        amount_pence = int(tx["amount"])
        
        # Early transfer flagger for Deduplication Logic
        is_transfer = 0
        if (
            description == "PAYMENT RECEIVED - THANK YOU"
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
                (ext_id, "amex", date_str, amount_pence, description, raw_category, is_transfer, None)
            )

            inserted_count += 1
        except sqlite3.Error as e:
            print(f"Database error inserting transaction {ext_id}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Successfully synced {inserted_count} new Amex transactions.")



# %%
if __name__ == "__main__":
    try:
        csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

        if not csv_files:
            print("Empty folder: No Amex CSV statements found to process.")

        else:
            print(f"Found {len(csv_files)} statements. Starting pipeline...")
            for file in csv_files:
                # Pass each individual file path into your processing logic
                transactions = import_amex_csv(file)
                save_amex_to_db(transactions)
                print(f"Finished processing: {os.path.basename(file)}")

    except Exception as e:
            print(f"Failed to sync Amex data: {e}")

# %%
