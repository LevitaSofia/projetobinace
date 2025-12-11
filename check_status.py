import ccxt
from dotenv import load_dotenv
import os

load_dotenv()

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
    'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
})

# Saldo
balance = exchange.fetch_balance()
usdt = balance['total'].get('USDT', 0)
bnb = balance['total'].get('BNB', 0)
brl = balance['total'].get('BRL', 0)
sol = balance['total'].get('SOL', 0)

# Preços
bnb_price = exchange.fetch_ticker('BNB/USDT')['last']
sol_price = exchange.fetch_ticker('SOL/USDT')['last']
usd_brl = exchange.fetch_ticker('USDT/BRL')['last']

# Valores
bnb_value = bnb * bnb_price
sol_value = sol * sol_price
total_usd = usdt + bnb_value + sol_value + (brl / usd_brl)
total_brl = total_usd * usd_brl

print("=" * 50)
print("📊 SALDO ATUAL")
print("=" * 50)
print(f"💵 USDT: ${usdt:.2f}")
print(f"🟡 BNB: {bnb:.6f} (${bnb_value:.2f})")
print(f"🟣 SOL: {sol:.6f} (${sol_value:.2f})")
print(f"🇧🇷 BRL: R$ {brl:.2f} (${brl/usd_brl:.2f})")
print("-" * 50)
print(f"💰 TOTAL: ${total_usd:.2f} (~R$ {total_brl:.2f})")
print("=" * 50)

# Trades recentes
print("\n📈 TRADES RECENTES:")
for symbol in ['BNB/USDT', 'SOL/USDT']:
    try:
        trades = exchange.fetch_my_trades(symbol, limit=5)
        if trades:
            print(f"\n  {symbol}:")
            for t in trades[-5:]:
                emoji = "🟢" if t['side'] == 'buy' else "🔴"
                print(f"    {emoji} {t['side'].upper()} {t['amount']:.4f} @ ${t['price']:.2f} = ${t['cost']:.2f}")
                print(f"       {t['datetime']}")
    except:
        pass

print("\n" + "=" * 50)
