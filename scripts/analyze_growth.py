
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime

DB_FILE = '/home/ubuntu/projetobinace/sandra_trading.db'

def analyze_growth():
    if not os.path.exists(DB_FILE):
        print(f"Database file not found: {DB_FILE}")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key='lab_state'")
        row = cursor.fetchone()
        conn.close()

        if not row:
            print("No lab_state found.")
            return

        lab_data = json.loads(row[0])
        strategies = lab_data.get('strategies', {})
        
        all_trades = []
        for strat_name, strat_data in strategies.items():
            trades = strat_data.get('trades', [])
            for t in trades:
                if 'net_profit_usdt' in t: # Only count closed trades with PnL
                    ts = t.get('timestamp')
                    # Parse simplified date (YYYY-MM-DD)
                    try:
                        dt = ts.split('T')[0]
                    except:
                        dt = 'Unknown'
                        
                    all_trades.append({
                        'date': dt,
                        'symbol': t.get('symbol'),
                        'profit_usdt': float(t.get('net_profit_usdt', 0)),
                        'profit_pct': float(t.get('net_profit_pct', 0))
                    })
        
        if not all_trades:
            print("No closed trades found.")
            return

        df = pd.DataFrame(all_trades)
        
        # Group by Date
        daily = df.groupby('date').agg(
            daily_profit_usdt=('profit_usdt', 'sum'),
            trades_count=('profit_usdt', 'count'),
            winning_trades=('profit_usdt', lambda x: (x > 0).sum())
        ).sort_index()
        
        daily['cumulative_profit'] = daily['daily_profit_usdt'].cumsum()
        
        print("\n=== CRESCIMENTO DIÁRIO DO CAPITAL (REAL) ===")
        print(daily.to_string(float_format="%.2f"))
        
        total_pnl = df['profit_usdt'].sum()
        print(f"\nLucro/Prejuízo Total Acumulado: ${total_pnl:.2f}")
        
        # Calculate Win Rate from dataframe
        wins = df[df['profit_usdt'] > 0]
        win_rate = (len(wins) / len(df)) * 100
        print(f"Taxa de Acerto Global: {win_rate:.1f}%")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_growth()
