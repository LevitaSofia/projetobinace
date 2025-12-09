"""
Script para verificar ordens reais na Binance - Com sincronização de timestamp
"""
import ccxt
import os
import time
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("🔍 VERIFICANDO CONTA BINANCE")
print("=" * 60)

# Primeiro pega o tempo do servidor
exchange_public = ccxt.binance({'enableRateLimit': True})
server_time = exchange_public.fetch_time()
local_time = int(time.time() * 1000)
time_diff = server_time - local_time

print(f"⏰ Tempo do servidor: {server_time}")
print(f"⏰ Tempo local: {local_time}")
print(f"⏰ Diferença: {time_diff}ms ({time_diff/1000:.1f} segundos)")

# Configuração da API COM correção de timestamp
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
    'options': {
        'defaultType': 'spot',
        'adjustForTimeDifference': True,
        'recvWindow': 60000,
        'timeDifference': time_diff  # Aplica a correção
    },
    'enableRateLimit': True
})

# Força sincronização
exchange.load_time_difference()

try:
    print("\n📊 SALDOS:")
    balance = exchange.fetch_balance()
    for currency, amount in balance['free'].items():
        if amount > 0.0001:
            total = balance['total'].get(currency, 0)
            print(f"  💰 {currency}: {total:.8f} (livre: {amount:.8f})")

    # Verificar trades executados
    print("\n💱 TRADES EXECUTADOS RECENTES:")
    symbols = ['SOL/USDT', 'USDT/BRL']
    for sym in symbols:
        try:
            trades = exchange.fetch_my_trades(sym, limit=10)
            if trades:
                print(f"\n  📈 {sym}:")
                for trade in trades[-5:]:
                    side = "🟢 COMPRA" if trade['side'] == 'buy' else "🔴 VENDA"
                    print(f"     {side} {trade['amount']:.6f} @ ${trade['price']:.4f}")
                    print(f"       Total: ${trade['cost']:.2f} | ID: {trade['id']}")
                    print(f"       Data: {trade['datetime']}")
        except Exception as e:
            print(f"  {sym}: {str(e)[:80]}")

except Exception as e:
    print(f"❌ Erro: {e}")

print("\n" + "=" * 60)
