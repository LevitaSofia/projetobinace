import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.binance_client import get_binance_client
from src.modules.data.candle_service import CandleService
from src.modules.risk.manager import RiskManager
from src.modules.strategy.cost_calculator import CostCalculator
from src.modules.treasury.bnb_manager import BNBTreasuryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VERIFY")

def test_system():
    logger.info("--- STARTING SYSTEM VERIFICATION ---")
    
    # 1. Check Infrastructure
    try:
        client = get_binance_client()
        logger.info("✅ Binance Client Initialized")
    except Exception as e:
        logger.error(f"❌ Binance Client Failed: {e}")
        return

    # 2. Check Data Engine
    try:
        cs = CandleService()
        df = cs.get_closed_candles('BTC/USDT', '1h', limit=5)
        if not df.empty:
            logger.info(f"✅ Data Engine: Fetched {len(df)} candles. Last Timestamp: {df.iloc[-1]['timestamp']}")
        else:
            logger.warning("⚠️ Data Engine: Returned empty dataframe (could be API issue or no data)")
    except Exception as e:
        logger.error(f"❌ Data Engine Failed: {e}")

    # 3. Check Risk Manager
    try:
        rm = RiskManager(max_daily_loss_usd=100)
        approved, msg = rm.check_entry_risk('BTC/USDT', 50)
        logger.info(f"✅ Risk Manager: Entry Check -> {approved} ({msg})")
    except Exception as e:
        logger.error(f"❌ Risk Manager Failed: {e}")

    # 4. Check Cost Calculator
    try:
        cc = CostCalculator()
        res = cc.calculate_min_profit_needed(1000, 0.01) # $10 pos
        logger.info(f"✅ Cost Calculator: Breakeven for $10 pos -> {res['breakeven_move_pct']:.4f}%")
    except Exception as e:
        logger.error(f"❌ Cost Calculator Failed: {e}")

    # 5. Check Treasury
    try:
        tm = BNBTreasuryManager()
        # We don't want to actually buy, just init
        logger.info("✅ Treasury Manager Initialized")
    except Exception as e:
        logger.error(f"❌ Treasury Manager Failed: {e}")

    logger.info("--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    test_system()
