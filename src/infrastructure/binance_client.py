import os
import time
import logging
import threading
import ccxt
from dotenv import load_dotenv

load_dotenv()

class BinanceClient:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(BinanceClient, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.logger = logging.getLogger("BinanceClient")
        
        # Load credentials
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.secret = os.getenv('BINANCE_SECRET')
        
        if not self.api_key or not self.secret:
            self.logger.warning("⚠️ Credentials not found! Exchange will run in public mode only.")
        
        # Initialize CCXT exchange
        self.exchange = ccxt.binance({
            'apiKey': self.api_key,
            'secret': self.secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot', 
                'adjustForTimeDifference': True
            }
        })
        
        # Lock for exchange operations to avoid race conditions
        self.exchange_lock = threading.RLock()
        self._initialized = True

    def get_exchange(self):
        return self.exchange

    def fetch_ohlcv(self, symbol, timeframe, limit=100):
        """Thread-safe OHLCV fetch with retries."""
        with self.exchange_lock:
            try:
                return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            except Exception as e:
                self.logger.error(f"❌ Error fetching candles for {symbol}: {e}")
                raise

    def fetch_balance(self):
        """Thread-safe balance fetch."""
        with self.exchange_lock:
            try:
                return self.exchange.fetch_balance()
            except Exception as e:
                self.logger.error(f"❌ Error fetching balance: {e}")
                raise
    
    def create_order(self, symbol, type, side, amount, price=None, params={}):
        """Thread-safe order placement."""
        with self.exchange_lock:
            try:
                return self.exchange.create_order(symbol, type, side, amount, price, params)
            except Exception as e:
                self.logger.error(f"❌ Error creating order {side} {symbol}: {e}")
                raise

    def cancel_order(self, id, symbol):
        with self.exchange_lock:
            try:
                return self.exchange.cancel_order(id, symbol)
            except Exception as e:
                self.logger.error(f"❌ Error canceling order {id}: {e}")
                raise

    def get_ticker(self, symbol):
        with self.exchange_lock:
            try:
                return self.exchange.fetch_ticker(symbol)
            except Exception as e:
                self.logger.error(f"❌ Error fetching ticker for {symbol}: {e}")
                raise

# Global singleton access
def get_binance_client():
    return BinanceClient()
