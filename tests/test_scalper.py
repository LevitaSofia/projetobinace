
import scalper_blindado
import requests

def fetch_raw_candles(symbol, interval='5m', limit=100):
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': symbol.replace('/', ''), 'interval': interval, 'limit': limit}
        response = requests.get(url, params=params, timeout=10)
        raw_data = response.json()
        clean_data = [x[:6] for x in raw_data] 
        return clean_data
    except Exception as e:
        print(f"Erro: {e}")
        return []

symbol = "PEPE/USDT"
print(f"Testing {symbol}...")
candles = fetch_raw_candles(symbol)
print(f"Candles: {len(candles)}")

if candles:
    # Debug BB columns
    import pandas as pd
    import pandas_ta as ta
    df = pd.DataFrame(candles, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['close'] = pd.to_numeric(df['close'])
    bb = ta.bbands(df['close'], length=20, std=2.0)
    print(f"BB Columns: {bb.columns.tolist()}")

    sinal, motivo, dados = scalper_blindado.analisar_sinal_hibrido(candles)
    print(f"Sinal: {sinal}")
    print(f"Motivo: {motivo}")
    print(f"Dados: {dados}")
else:
    print("No candles fetched")
