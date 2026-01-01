import pandas as pd
import time
import logging
from datetime import datetime, timedelta
from src.infrastructure.binance_client import get_binance_client

class CandleService:
    def __init__(self):
        self.client = get_binance_client()
        self.logger = logging.getLogger("CandleService")

    def get_closed_candles(self, symbol, timeframe, limit=100):
        """
        Fetches candles and ensures the last one is CLOSED.
        If the last candle is still open (based on timestamp), it is dropped.
        """
        ohr_raw = self.client.fetch_ohlcv(symbol, timeframe, limit=limit + 1)
        if not ohr_raw:
            return pd.DataFrame()

        df = pd.DataFrame(ohr_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Calculate expected close time of the last candle
        # We assume timeframe is standard like '1m', '5m', '1h'
        last_ts = df.iloc[-1]['timestamp']
        current_time = datetime.utcnow()
        
        # Simple duration parsing (can be made more robust)
        duration_min = 0
        if timeframe.endswith('m'):
            duration_min = int(timeframe[:-1])
        elif timeframe.endswith('h'):
            duration_min = int(timeframe[:-1]) * 60
        elif timeframe.endswith('d'):
            duration_min = int(timeframe[:-1]) * 60 * 24

        candle_end_time = last_ts + timedelta(minutes=duration_min)

        # If current time < candle end time, it's OPEN. Drop it.
        if current_time < candle_end_time:
            # self.logger.debug(f"Dropping open candle for {symbol} at {last_ts}")
            df = df.iloc[:-1]
        
        return df

    def get_latest_close(self, symbol, timeframe):
        df = self.get_closed_candles(symbol, timeframe, limit=5)
        if df.empty:
            return None
        return df.iloc[-1]
