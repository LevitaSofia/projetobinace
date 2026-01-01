
import sqlite3
import pandas as pd
import os

DB_FILE = '/home/ubuntu/projetobinace/sandra_trading.db'

def analyze_trades():
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT symbol, profit_pct, profit_usdt, side, timestamp FROM trade_history"
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            print("No trades found in the database.")
            return

        # Clean symbol names if needed (sometimes they have /USDT)
        df['symbol'] = df['symbol'].astype(str)
        
        # Filter for actual trades (ensure profit is numeric)
        df['profit_pct'] = pd.to_numeric(df['profit_pct'], errors='coerce').fillna(0)
        df['profit_usdt'] = pd.to_numeric(df['profit_usdt'], errors='coerce').fillna(0)

        # Group by symbol
        stats = df.groupby('symbol').agg(
            total_trades=('symbol', 'count'),
            avg_profit_pct=('profit_pct', 'mean'),
            sum_profit_pct=('profit_pct', 'sum'),
            total_profit_usdt=('profit_usdt', 'sum'),
            win_rate=('profit_usdt', lambda x: (x > 0).mean() * 100)
        ).reset_index()

        # Sort by total trades descending
        stats = stats.sort_values(by='total_trades', ascending=False)

        print("\n--- Trade Analysis by Symbol ---")
        print(stats.to_string(index=False, float_format="%.2f"))
        
        print("\n--- ETH Analysis ---")
        eth_stats = stats[stats['symbol'].str.contains('ETH')]
        if not eth_stats.empty:
            print(eth_stats.to_string(index=False, float_format="%.2f"))
        else:
            print("No ETH trades found.")

        print("\n--- Overall Stats ---")
        print(f"Total Trades: {len(df)}")
        print(f"Total Profit USDT: {df['profit_usdt'].sum():.2f}")
        print(f"Average Profit %: {df['profit_pct'].mean():.2f}%")

    except Exception as e:
        print(f"Error analyzing trades: {e}")

if __name__ == "__main__":
    analyze_trades()
