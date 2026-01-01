import pandas_ta as ta
import logging

class RSIStrategy:
    def __init__(self, params=None):
        self.logger = logging.getLogger("RSIStrategy")
        self.params = params or {}
        self.rsi_period = self.params.get('RSI_PERIOD', 14)
        self.rsi_buy_threshold = self.params.get('RSI_BUY', 30)
        self.rsi_sell_threshold = self.params.get('RSI_SELL', 70)

    def calculate_indicators(self, df):
        if df.empty:
            return df
        
        # Calculate RSI using pandas_ta
        df['rsi'] = ta.rsi(df['close'], length=self.rsi_period)
        
        # Add Bollinger Bands for context (volatility)
        bb = ta.bbands(df['close'], length=20, std=2)
        if bb is not None:
             df = df.join(bb)
        
        return df

    def get_signal(self, df):
        """
        Returns:
            dict: { 'action': 'BUY'|'SELL'|'HOLD', 'rsi': float, 'confidence': float, 'reason': str }
        """
        if df.empty or len(df) < self.rsi_period:
            return {'action': 'HOLD', 'reason': 'Not enough data'}

        last_row = df.iloc[-1]
        rsi = last_row['rsi']
        
        # Logic from User Request: "RSI (Wilder), apenas candle fechado"
        # We assume df only has closed candles provided by CandleService.

        # Simple RSI Strategy with Cooldown check (logic handled by state machine or here?)
        # For now, pure signal logic.
        
        action = 'HOLD'
        reason = f"RSI {rsi:.2f} in neutral zone"

        if rsi <= self.rsi_buy_threshold:
            action = 'BUY'
            reason = f"RSI {rsi:.2f} <= {self.rsi_buy_threshold} (Oversold)"
        elif rsi >= self.rsi_sell_threshold:
            action = 'SELL'
            reason = f"RSI {rsi:.2f} >= {self.rsi_sell_threshold} (Overbought)"

        return {
            'action': action,
            'rsi': rsi,
            'price': last_row['close'],
            'timestamp': last_row['timestamp'],
            'reason': reason
        }
