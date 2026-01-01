import ccxt
import os
import pandas as pd
import pandas_ta as ta
import sys
from dotenv import load_dotenv

# Load env from parent dir
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')

def diagnose_wld():
    if not API_KEY or not SECRET:
        print("❌ Sem credenciais.")
        return

    exchange = ccxt.binance({'apiKey': API_KEY, 'secret': SECRET})
    symbol = 'WLD/USDT'
    
    print(f"🔍 Diagnostico WLD ({symbol})...")
    
    # 1. Checa Saldo
    try:
        balance = exchange.fetch_balance()
        wld_free = balance.get('WLD', {}).get('free', 0)
        wld_used = balance.get('WLD', {}).get('used', 0)
        wld_total = balance.get('WLD', {}).get('total', 0)
        print(f"💰 Saldo WLD: Livre={wld_free} | Usado={wld_used} | Total={wld_total}")
        
        # Pega preço atual
        ticker = exchange.fetch_ticker(symbol)
        price = float(ticker['last'])
        print(f"💵 Preço Atual: ${price:.4f}")
        
        value_usdt = wld_total * price
        print(f"💎 Valor em USDT: ${value_usdt:.4f}")
        
        if value_usdt < 0.5:
            print("⚠️ AVISO: Valor menor que 0.5 USDT. O relatório ignora 'poeira' (dust).")
    except Exception as e:
        print(f"❌ Erro ao ler saldo: {e}")

    # 2. Checa RSI Atual (15m)
    try:
        candles = exchange.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # RSI Classico 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_classic'] = 100 - (100 / (1 + rs))
        
        # RSI Pandas TA (RMA - Wilder)
        try:
            df.ta.rsi(length=14, append=True)
            rsi_ta = df['RSI_14'].iloc[-1]
        except:
            rsi_ta = 0

        rsi_calc_classic = df['rsi_classic'].iloc[-1]
        
        print(f"📊 RSI (15m) Calculado agora:")
        print(f"   - Método Clássico (Simple): {rsi_calc_classic:.2f}")
        print(f"   - Método Wilder (Padrão Binance): {rsi_ta:.2f}")
        
    except Exception as e:
         print(f"❌ Erro ao calcular RSI: {e}")

if __name__ == "__main__":
    diagnose_wld()
