import logging
from datetime import datetime
from src.infrastructure.binance_client import get_binance_client

class RiskManager:
    def __init__(self, max_daily_loss_usd=50.0, max_trades_per_day=20, max_position_size_usd=100.0):
        self.client = get_binance_client()
        self.logger = logging.getLogger("RiskManager")
        
        self.max_daily_loss_usd = max_daily_loss_usd
        self.max_trades_per_day = max_trades_per_day
        self.max_position_size_usd = max_position_size_usd
        
        # In-memory state (should be persisted in DB in production)
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.last_reset = datetime.utcnow().date()
        self.kill_switch_active = False

    def _reset_daily_stats_if_needed(self):
        current_date = datetime.utcnow().date()
        if current_date > self.last_reset:
            self.daily_pnl = 0.0
            self.trades_today = 0
            self.last_reset = current_date
            self.kill_switch_active = False # Optional: Auto-reset kill switch next day?

    def check_entry_risk(self, symbol, amount_usd):
        self._reset_daily_stats_if_needed()

        if self.kill_switch_active:
            return False, "KILL SWITCH ACTIVE"

        if self.daily_pnl <= -self.max_daily_loss_usd:
            self.kill_switch_active = True
            return False, f"Daily Loss Limit Hit ({self.daily_pnl})"

        if self.trades_today >= self.max_trades_per_day:
            return False, f"Max Trades Per Day Hit ({self.trades_today})"
            
        if amount_usd > self.max_position_size_usd:
            return False, f"Position Size {amount_usd} > Max {self.max_position_size_usd}"

        # Check circuit breaker / market sanity? (e.g. check spread > 1% -> too volatile?)
        
        return True, "Approved"

    def record_completed_trade(self, pnl_usd):
        self._reset_daily_stats_if_needed()
        self.trades_today += 1
        self.daily_pnl += pnl_usd
        
        if self.daily_pnl <= -self.max_daily_loss_usd:
            self.logger.critical(f"⚠️ DAILY LOSS LIMIT HIT: {self.daily_pnl}. ACTIVATING KILL SWITCH.")
            self.kill_switch_active = True
