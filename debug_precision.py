
import ccxt
import sys

def test_precision():
    exchange = ccxt.binance()
    try:
        exchange.load_markets()
        symbol = 'SOL/USDT'
        market = exchange.market(symbol)
        print(f"Symbol: {symbol}")
        print(f"Precision: {market['precision']}")
        print(f"Limits: {market['limits']}")
        
        amounts = [0.0899, 0.0005, 0.001, 0.0011, 0.0009]
        for amt in amounts:
            prec = exchange.amount_to_precision(symbol, amt)
            print(f"Amount: {amt} -> Precision: {prec} (Type: {type(prec)})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_precision()
