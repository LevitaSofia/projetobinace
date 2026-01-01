import sqlite3
import logging
import threading
import os

DB_PATH = os.path.join(os.getcwd(), 'sandra_trading.db')

class DatabaseManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = DB_PATH
        self.logger = logging.getLogger("DatabaseManager")
        self._check_schema()
        self._initialized = True

    def get_connection(self):
        """Returns a new connection (SQLite connections are not thread-safe)."""
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _check_schema(self):
        """Ensures basic tables exist."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Tabela de Trades (simplificada por enquanto)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    side TEXT,
                    amount REAL,
                    price REAL,
                    cost REAL,
                    fee REAL,
                    fee_currency TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    strategy_data TEXT
                )
            ''')
            
            # Tabela de Métricas (novo)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT,
                    value REAL,
                    tags TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
        except Exception as e:
            self.logger.error(f"DB Schema Check Failed: {e}")
        finally:
            conn.close()

    def log_metric(self, name, value, tags=None):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO metrics (metric_name, value, tags) VALUES (?, ?, ?)", (name, value, str(tags)))
            conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to log metric: {e}")
        finally:
            conn.close()

# Singleton accessor
def get_db():
    return DatabaseManager()
