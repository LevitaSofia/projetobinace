import logging
import time
from src.infrastructure.binance_client import get_binance_client

class BNBTreasuryManager:
    def __init__(self, min_bnb_usdt=5.0, target_bnb_usdt=20.0):
        self.client = get_binance_client()
        self.logger = logging.getLogger("BNBTreasury")
        self.min_bnb_usdt = min_bnb_usdt
        self.target_bnb_usdt = target_bnb_usdt

    def check_and_topup_bnb(self):
        """
        Checks if BNB balance is sufficient for fees.
        If Value(BNB) < min_bnb_usdt, buys enough to reach target_bnb_usdt.
        """
        try:
            # 1. Get Balances
            balances = self.client.fetch_balance()
            bnb_free = balances['free'].get('BNB', 0.0)
            usdt_free = balances['free'].get('USDT', 0.0)
            
            # 2. Get BNB Price
            ticker = self.client.get_ticker('BNB/USDT')
            bnb_price = ticker['last']
            
            bnb_value_usdt = bnb_free * bnb_price
            
            self.logger.info(f"💰 BNB Treasury: Holding {bnb_free:.4f} BNB (~${bnb_value_usdt:.2f})")
            
            # 3. Decision
            if bnb_value_usdt < self.min_bnb_usdt:
                shortfall_usdt = self.target_bnb_usdt - bnb_value_usdt
                
                # Minimum order size check (Binance usually $5 or $10)
                if shortfall_usdt < 6.0: 
                    shortfall_usdt = 6.0 # Force min trade size if we are topping up
                
                if usdt_free < shortfall_usdt:
                    self.logger.warning(f"⚠️ Not enough USDT to topup BNB. Need ${shortfall_usdt}, have ${usdt_free}")
                    return False
                
                amount_to_buy = shortfall_usdt / bnb_price
                
                self.logger.info(f"📉 BNB Low! Buying {amount_to_buy:.4f} BNB (~${shortfall_usdt})")
                
                # Execute Market Buy for simplicity and speed (fees are critical)
                order = self.client.create_order('BNB/USDT', 'market', 'buy', amount_to_buy)
                self.logger.info(f"✅ BNB Topup Complete: {order.get('id')}")
                return True
                
            return False

        except Exception as e:
            self.logger.error(f"❌ BNB Treasury Error: {e}")
            return False
