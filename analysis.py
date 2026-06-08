#%%
#This will contain historical analysis etc
import sqlite3
import matplotlib.pyplot as plt

def generate_balance_pie_chart(db_path="finance.db", output_filename="plots/balance_pie_chart.png"):
    """
    Queries the database for the latest balance of each account, 
    calculates the net worth, and saves a clean pie chart distribution.
    """
    # 1. Connect and query the latest snapshot for each unique account
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT account, balance 
    FROM balances b
    WHERE date = (SELECT MAX(date) FROM balances WHERE account = b.account);
    """
    
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Database error: {e}. Ensure the balances table exists.")
        return
    finally:
        conn.close()
        
    if not rows:
        print("No balance data found to plot.")
        return

    # 2. Extract data and convert pence integers to pound floats
    accounts = [row[0].upper() for row in rows]
    balances_pounds = [row[1] / 100.0 for row in rows]
    total_net_worth = sum(balances_pounds)

    # 3. Format the labels to show the account name and exact value cleanly
    labels = [f"{acc}\n(£{bal:,.2f})" for acc, bal in zip(accounts, balances_pounds)]

    # 4. Generate the Plot (Avoiding .figure() as per styling guidelines)
    # Define a clean, modern color palette
    colors = ['#2ec4b6', '#ff9f1c', '#e71d36', '#011627', '#4cc9f0']
    
    plt.pie(
        balances_pounds, 
        labels=labels, 
        autopct='%1.1f%%', 
        startangle=140, 
        colors=colors[:len(accounts)],
        pctdistance=0.85,    # Moves percentages inside slightly for readability
        labeldistance=1.1    # Pushes the text labels outside neatly to prevent overlap
    )
    
    # Draw a white circle in the center to turn it into a clean donut chart (Optional but looks great)
    centre_circle = plt.Circle((0,0), 0.70, fc='white')
    plt.gca().add_artist(centre_circle)
    
    # Ensure pie is drawn as a perfect circle
    plt.axis('equal')  

    # 5. Dynamic Title showing the overall total at the top
    plt.title(
        f"Total Asset Valuation: £{total_net_worth:,.2f}", 
        fontsize=14, 
        fontweight='bold', 
        pad=30
    )
    
    # 6. Save the chart cleanly
    plt.tight_layout()
    plt.savefig(output_filename, dpi=300)
    plt.close()
    
    print(f"Success! Balance pie chart saved as '{output_filename}'")

if __name__ == "__main__":
    # You can call this directly to test it
    generate_balance_pie_chart()
# %%
