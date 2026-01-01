
import ccxt
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')

def check_today():
    if not API_KEY or not SECRET:
        print("❌ Sem credenciais.")
        return

    exchange = ccxt.binance({'apiKey': API_KEY, 'secret': SECRET})
    
    # 24h atrás até agora
    since = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)
    
    print(f"🔍 Buscando trades na Binance desde ontem...")
    
    # Verifica em algumas moedas comuns (add more if needed)
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'USDC/USDT', 'ICP/USDT', 'WLD/USDT', 'LTC/USDT']
    found = False
    
    for symbol in symbols:
        try:
            trades = exchange.fetch_my_trades(symbol, since=since)
            if trades:
                for t in trades:
                    dt = datetime.fromtimestamp(t['timestamp']/1000)
                    print(f"✅ ACHADO: {t['symbol']} | {t['side'].upper()} | Data: {dt} | Qtd: {t['amount']} | Preço: {t['price']}")
                    found = True
        except Exception as e:
            print(f"⚠️ Erro em {symbol}: {e}")

    if not found:
        print("⛔ Nenhum trade encontrado na Binance nas últimas 24h.")
    else:
        print("⚠️ Se apareceu acima, o bot falhou em salvar no banco.")

if __name__ == "__main__":
    check_today()
