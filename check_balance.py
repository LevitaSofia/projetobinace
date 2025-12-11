import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

print("⏰ Conectando à Binance...")

# Primeiro, obtém a diferença de tempo
exchange_temp = ccxt.binance({'enableRateLimit': True})
try:
    server_time = exchange_temp.fetch_time()
    local_time = int(time.time() * 1000)
    time_diff = server_time - local_time
    print(f"⏰ Diferença de tempo: {time_diff}ms")
except Exception as e:
    print(f"⚠️ Erro ao obter tempo: {e}")
    time_diff = 0

# Cria exchange com configs
e = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
        'recvWindow': 60000,
        'timeDifference': time_diff
    }
})

# Força sincronização
print("⏳ Sincronizando relógio...")
try:
    diff = e.load_time_difference()
    print(f"✅ Relógio sincronizado. Diferença: {diff}ms")
except Exception as err:
    print(f"⚠️ Erro na sincronização: {err}")

# Busca saldo
print("\n" + "=" * 50)
print("💰 SALDOS NA BINANCE")
print("=" * 50)

b = e.fetch_balance()
usdt = b['free'].get('USDT', 0)
bnb = b['free'].get('BNB', 0)

print(f"USDT: ${usdt:.8f}")
print(f"BNB:  {bnb:.8f}")

# Valor do BNB em USDT
ticker = e.fetch_ticker('BNB/USDT')
bnb_value = bnb * ticker['last']
print(f"BNB em USDT: ${bnb_value:.4f}")
print(f"\n💵 TOTAL: ${usdt + bnb_value:.2f}")
print("=" * 50)

# Últimas ordens
print("\n📜 ÚLTIMOS TRADES BNB/USDT:")
try:
    trades = e.fetch_my_trades('BNB/USDT', limit=5)
    for t in trades:
        emoji = "🟢" if t['side'] == 'buy' else "🔴"
        print(f"  {emoji} {t['datetime'][:19]} | {t['side'].upper():4} | {t['amount']:.6f} BNB @ ${t['price']:.2f}")
except Exception as err:
    print(f"  ⚠️ Erro ao buscar trades: {err}")
