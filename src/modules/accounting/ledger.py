import logging
from src.infrastructure.db import get_db

class Ledger:
    def __init__(self):
        self.db = get_db()
        self.logger = logging.getLogger("Ledger")

    def record_trade(self, trade_data):
        """
        Records a trade execution.
        trade_data: dict containing symbol, side, amount, price, cost, fee, strategy info
        """
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (symbol, side, amount, price, cost, fee, fee_currency, strategy_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('symbol'),
                trade_data.get('side'),
                trade_data.get('amount'),
                trade_data.get('price'),
                trade_data.get('cost'),
                trade_data.get('fee', 0.0),
                trade_data.get('fee_currency', 'BNB'),
                str(trade_data.get('strategy_data', {}))
            ))
            conn.commit()
            self.logger.info(f"📝 Trade recorded in Ledger: {trade_data.get('symbol')} {trade_data.get('side')}")
        except Exception as e:
            self.logger.error(f"❌ Failed to record trade: {e}")
        finally:
            conn.close()

    def get_todays_metrics(self):
        # Placeholder for reporting query
        pass
