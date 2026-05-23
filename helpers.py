# Function to read database - give it an SQL function
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")

def query_db(sql_string: str):
    """Executes a custom SQL query string and prints/returns the results cleanly."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_string)
        
        # If it's a SELECT statement, fetch and display rows
        if cursor.description:
            # Grab column names from the cursor description
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            
            print(f"--- Query Results ({len(rows)} rows) ---")
            print(" | ".join(columns))
            print("-" * 40)
            for row in rows:
                print(row)
            return rows
        else:
            # If it's an INSERT/UPDATE/DELETE statement
            conn.commit()
            print(f"Success: Query executed. Rows affected: {cursor.rowcount}")
            return cursor.rowcount
            
    except sqlite3.Error as e:
        print(f"SQL Error: {e}")
    finally:
        conn.close()