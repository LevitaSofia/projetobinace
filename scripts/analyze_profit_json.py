
import sqlite3
import pandas as pd
import json
import os

DB_FILE = '/home/ubuntu/projetobinace/sandra_trading.db'

def analyze_trades_from_json():
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
            print("No lab_state found in system_state.")
            return

        lab_data = json.loads(row[0])
        aggressive_data = lab_data.get('strategies', {}).get('aggressive', {})
        trades = aggressive_data.get('trades', [])

        if not trades:
            print("No trades found in 'aggressive' strategy.")
            return

        # Convert to DataFrame
        trade_list = []
        for t in trades:
            # We only care about closed trades (SELLs usually have the profit info)
            # Or pair if it has net_profit_pct
            if 'net_profit_pct' in t:
                trade_list.append({
                    'symbol': t.get('symbol'),
                    'profit_pct': t.get('net_profit_pct', 0),
                    'profit_usdt': t.get('net_profit_usdt', 0),
                    'timestamp': t.get('timestamp')
                })
        
        if not trade_list:
             print("No closed trades with profit data found.")
             return

        df = pd.DataFrame(trade_list)
        
        # Clean numeric columns
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

        print("\n=== ANÁLISE DE LUCRO POR MOEDA (BASE DE DADOS JSON) ===")
        print(stats.to_string(index=False, float_format="%.2f"))
        
        print("\n=== DETALHE ETH ===")
        eth_stats = stats[stats['symbol'].str.contains('ETH')]
        if not eth_stats.empty:
            print(eth_stats.to_string(index=False, float_format="%.2f"))
        else:
            print("Nenhum trade de ETH encontrado.")

        print("\n=== RESUMO GERAL ===")
        print(f"Total de Trades: {len(df)}")
        print(f"Lucro Total (USDT): ${df['profit_usdt'].sum():.2f}")
        print(f"Média de Lucro (%): {df['profit_pct'].mean():.2f}%")

    except Exception as e:
        print(f"Error analyzing trades: {e}")

if __name__ == "__main__":
    analyze_trades_from_json()
