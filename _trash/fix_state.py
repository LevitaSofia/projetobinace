import sqlite3
import json
import time
from datetime import datetime
import ccxt

DB_NAME = "sandra_trading.db"

def get_current_prices():
    try:
        exchange = ccxt.binance()
        tickers = exchange.fetch_tickers(['ETH/USDT', 'SOL/USDT'])
        return {
            'ETH/USDT': tickers['ETH/USDT']['last'],
            'SOL/USDT': tickers['SOL/USDT']['last']
        }
    except Exception as e:
        print(f"⚠️ Erro ao buscar preços atuais: {e}")
        return {'ETH/USDT': 3000.0, 'SOL/USDT': 130.0} # Fallback

def fix_db():
    print("🔧 Iniciando correção do banco de dados...")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM system_state WHERE key = 'lab_state'")
    row = cursor.fetchone()
    
    if not row:
        print("❌ Estado não encontrado no DB.")
        return

    state = json.loads(row[0])
    strategy = state.get('strategies', {}).get('aggressive', {})
    
    # 1. Corrigir Duplicidade (Remover 'position' legado)
    if 'position' in strategy:
        print("🧹 Removendo campo 'position' duplicado (legado)...")
        del strategy['position']
    else:
        print("✅ Campo 'position' (legado) não encontrado (ok).")
    
    # 2. Adicionar Moedas Faltando (ETH, SOL)
    if 'positions' not in strategy:
        strategy['positions'] = {}
        
    positions = strategy['positions']
    
    prices = get_current_prices()
    
    # ETH
    if 'ETH/USDT' not in positions:
        price = prices.get('ETH/USDT', 3000.0)
        print(f"➕ Adicionando ETH/USDT (0.0037) @ ${price}...")
        positions['ETH/USDT'] = {
            "symbol": "ETH/USDT",
            "qty": 0.0037,
            "entry_price": price,
            "entry_time": datetime.now().isoformat(),
            "trail_active": False,
            "entry_cost_usdt": 0.0037 * price,
            "log_entry": "Importado via fix_state.py"
        }
    else:
        print("ℹ️ ETH/USDT já está monitorado.")

    # SOL
    if 'SOL/USDT' not in positions:
        price = prices.get('SOL/USDT', 130.0)
        print(f"➕ Adicionando SOL/USDT (0.0899) @ ${price}...")
        positions['SOL/USDT'] = {
            "symbol": "SOL/USDT",
            "qty": 0.0899,
            "entry_price": price,
            "entry_time": datetime.now().isoformat(),
            "trail_active": False,
            "entry_cost_usdt": 0.0899 * price,
            "log_entry": "Importado via fix_state.py"
        }
    else:
        print("ℹ️ SOL/USDT já está monitorado.")

    # Salvar de volta
    state['strategies']['aggressive'] = strategy
    new_json = json.dumps(state)
    
    cursor.execute("UPDATE system_state SET value = ? WHERE key = 'lab_state'", (new_json,))
    conn.commit()
    print("✅ Banco de dados atualizado com sucesso!")
    conn.close()

if __name__ == "__main__":
    fix_db()
