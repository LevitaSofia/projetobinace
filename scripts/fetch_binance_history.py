
import os
import ccxt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')

def fetch_history():
    if not API_KEY or not SECRET:
        print("❌ Sem credenciais da Binance no .env")
        return

    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True
    })

    # Pares para verificar
    symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 'LTC/USDT']
    
    print(f"🔍 Buscando histórico direto na Binance (últimos 15 dias)...")
    
    found_any = False
    for symbol in symbols:
        try:
            # Pega trades desde 15 de Dezembro
            since = exchange.parse8601('2025-12-15T00:00:00Z')
            trades = exchange.fetch_my_trades(symbol, since=since)
            
            if trades:
                print(f"\n--- {symbol} ({len(trades)} trades) ---")
                found_any = True
                for t in trades:
                    dt = t['datetime']
                    side = t['side'].upper()
                    price = t['price']
                    qty = t['amount']
                    cost = t['cost']
                    print(f"[{dt}] {side} {qty} @ {price} (Total: ${cost:.2f})")
        except Exception as e:
            print(f"Erro ao ler {symbol}: {e}")

    if not found_any:
        print("\n🤷‍♂️ Nenhum trade encontrado na Binance desde o dia 15/Dez.")
    else:
        print("\n✅ Fim da busca.")

if __name__ == "__main__":
    fetch_history()
