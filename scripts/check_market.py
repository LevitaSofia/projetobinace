
import os
import ccxt
import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_market():
    if not API_KEY or not SECRET:
        print("❌ Sem credenciais.")
        return

    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True
    })

    symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 'LTC/USDT']
    
    print(f"🔎 Analisando Mercado agora (Timeframe: 5m)...")
    print(f"{'MOEDA':<10} | {'RSI':<6} | {'PREÇO ($)':<12} | {'STATUS'}")
    print("-" * 50)
    
    for symbol in symbols:
        try:
            # Pega 50 velas de 5 minutos
            candles = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=50)
            df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            
            # Calcula RSI simples
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            current_rsi = df['rsi'].iloc[-1]
            current_price = df['close'].iloc[-1]
            
            status = "⚪ AGUARDANDO"
            if current_rsi < 35:
                status = "✅ PONTO DE COMPRA!"
            elif current_rsi < 45:
                status = "🟡 QUASE LÁ"
            elif current_rsi > 70:
                status = "🔴 SOBRECOMPRADO"
                
            print(f"{symbol:<10} | {current_rsi:>5.1f}  | {current_price:>12.2f} | {status}")
            
        except Exception as e:
            print(f"Erro {symbol}: {e}")

if __name__ == "__main__":
    check_market()
