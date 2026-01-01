import logging

class CostCalculator:
    def __init__(self, maker_fee=0.00075, taker_fee=0.00075):
        # Default BNB fee discount (0.075%)
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.logger = logging.getLogger("CostCalculator")

    def calculate_min_profit_needed(self, price, amount, slippage_pct=0.001):
        """
        Calculate if the trade is worth it based on fees + slippage.
        Rule: Expected Move > (EntryFee + ExitFee + Spread + Slippage)
        """
        # Entry cost
        pos_value = price * amount
        entry_fee = pos_value * self.taker_fee # Conservative assumption: Taker entry
        
        # Exit cost (estimated same price for fee calc)
        exit_fee = pos_value * self.taker_fee
        
        # Slippage cost (entry + exit)
        slippage_cost = pos_value * slippage_pct * 2
        
        total_cost = entry_fee + exit_fee + slippage_cost
        
        breakeven_move_pct = (total_cost / pos_value) * 100
        
        return {
            'total_cost_usd': total_cost,
            'breakeven_move_pct': breakeven_move_pct
        }

    def check_trade_viability(self, expected_profit_pct, breakeven_pct):
        return expected_profit_pct > breakeven_pct
