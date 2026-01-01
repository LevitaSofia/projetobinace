import time
import logging
from enum import Enum
from src.modules.data.candle_service import CandleService
from src.modules.strategy.rsi_strategy import RSIStrategy
from src.modules.strategy.cost_calculator import CostCalculator
from src.modules.risk.manager import RiskManager
from src.modules.execution.orders import ExecutionEngine
from src.modules.treasury.bnb_manager import BNBTreasuryManager
from src.modules.accounting.ledger import Ledger

class State(Enum):
    SYNC = 1
    CHECK_BNB = 2
    WAIT_CANDLE_CLOSE = 3
    CALC_SIGNAL = 4
    RISK_CHECK = 5
    COST_CHECK = 6
    PLACE_ORDER = 7
    MONITOR_ORDER = 8
    SLEEP = 99

class BotStateMachine:
    def __init__(self, symbols, timeframe='1h'):
        self.logger = logging.getLogger("StateMatching")
        self.symbols = symbols
        self.timeframe = timeframe
        self.current_state = State.SYNC
        
        # Modules
        self.data_engine = CandleService()
        self.strategy_engine = RSIStrategy()
        self.risk_manager = RiskManager()
        self.execution_engine = ExecutionEngine()
        self.treasury_manager = BNBTreasuryManager()
        self.ledger = Ledger()
        self.cost_calculator = CostCalculator()
        
        # Intelligence
        from src.modules.intelligence.ai_service import AIService
        self.ai_service = AIService()

        # Runtime State
        self.targets = {} # {symbol: {action, amount, price...}}

    def run(self):
        self.logger.info("🤖 Bot Started. Entering State Machine Loop...")
        while True:
            try:
                self._tick()
                time.sleep(1) # Main tick loop
            except KeyboardInterrupt:
                self.logger.info("🛑 Bot Stopped by User.")
                break
            except Exception as e:
                self.logger.error(f"💥 Critical Error in State Machine: {e}", exc_info=True)
                time.sleep(10) # Backoff on error

    def _tick(self):
        if self.current_state == State.SYNC:
            self.logger.info("🔄 SYNC: Sincronizando dados...")
            # TODO: Sync logic if needed
            self.current_state = State.CHECK_BNB

        elif self.current_state == State.CHECK_BNB:
            self.logger.info("💰 CHECK_BNB: Verificando taxas...")
            self.treasury_manager.check_and_topup_bnb()
            self.current_state = State.WAIT_CANDLE_CLOSE

        elif self.current_state == State.WAIT_CANDLE_CLOSE:
            # Here we just wait or move on. 
            # Ideally we check if a new candle just closed.
            # For simplicity in this loop, we just move to Calc.
            # Real impl would check time.
            self.current_state = State.CALC_SIGNAL

        elif self.current_state == State.CALC_SIGNAL:
            self.logger.info("🧠 CALC_SIGNAL: Analisando mercado...")
            self.targets = {}
            for symbol in self.symbols:
                df = self.data_engine.get_closed_candles(symbol, self.timeframe)
                signal = self.strategy_engine.get_signal(df)
                
                if signal['action'] != 'HOLD':
                    self.logger.info(f"💡 Algorithmic Signal found for {symbol}: {signal}")
                    
                    # --- AI ANALYSIS ---
                    if self.ai_service.enabled:
                        self.logger.info(f"🤖 Asking Sandra (AI) about {symbol}...")
                        
                        # Prepare context
                        # We need calculated volatility and trend, simplified here
                        market_data = {
                            'price': signal.get('price'),
                            'rsi': signal.get('rsi'),
                            'volatility': 0.02, # Placeholder, should come from strategy
                            'trend': 'Neutral', # Should come from strategy
                            'cost_pct': 0.002
                        }
                        
                        ai_decision = self.ai_service.analyze_trade(symbol, market_data)
                        
                        if ai_decision:
                            self.logger.info(f"🧠 AI Response: {ai_decision}")
                            if ai_decision.get('action') == 'CANCEL':
                                self.logger.warning(f"🚫 AI VETOED trade for {symbol}: {ai_decision.get('reason')}")
                                continue # Skip this target
                            
                            # Log AI advice
                            signal['ai_reason'] = ai_decision.get('reason')
                            signal['ai_confidence'] = ai_decision.get('confidence')
                    
                    self.targets[symbol] = signal
            
            if self.targets:
                self.current_state = State.RISK_CHECK
            else:
                self.logger.info("💤 No signals. Sleeping...")
                self._sleep_until_next_period()
                self.current_state = State.CHECK_BNB # Loop back

        elif self.current_state == State.RISK_CHECK:
            approved_targets = {}
            for symbol, signal in self.targets.items():
                amount_usd = 20.0 # Fixed for now, can be dynamic
                approved, reason = self.risk_manager.check_entry_risk(symbol, amount_usd)
                if approved:
                    self.logger.info(f"✅ Risk Approved for {symbol}")
                    signal['amount_usd'] = amount_usd
                    approved_targets[symbol] = signal
                else:
                    self.logger.warning(f"🛡️ Risk Rejected for {symbol}: {reason}")
            
            self.targets = approved_targets
            if self.targets:
                self.current_state = State.COST_CHECK
            else:
                self.current_state = State.WAIT_CANDLE_CLOSE

        elif self.current_state == State.COST_CHECK:
            # Check if profit potential > fees
            # Creating naive assumption on profit potential from strategy or fixed
            final_targets = {}
            for symbol, signal in self.targets.items():
                # Simplified check
                viability = self.cost_calculator.calculate_min_profit_needed(signal['price'], signal['amount_usd'] / signal['price'])
                self.logger.info(f"💲 Cost Check {symbol}: Breakeven at {viability['breakeven_move_pct']:.4f}%")
                # Assuming we want at least 0.5% move?
                if viability['breakeven_move_pct'] < 0.5:
                    final_targets[symbol] = signal
                else:
                    # If fees are too high relative to position? (Actually low pct is good here, wait logic inverted?)
                    # Breakeven pct = (Cost / Pos) * 100. Lower is better.
                    # If breakeven is > 1%, it's too expensive to trade.
                    if viability['breakeven_move_pct'] < 1.0: # Acceptable cost
                         final_targets[symbol] = signal
            
            self.targets = final_targets
            if self.targets:
                self.current_state = State.PLACE_ORDER
            else:
                self.current_state = State.WAIT_CANDLE_CLOSE

        elif self.current_state == State.PLACE_ORDER:
            for symbol, signal in self.targets.items():
                side = signal['action'].lower()
                amount = signal['amount_usd'] / signal['price']
                # Precision adjustment needed here theoretically
                
                order = self.execution_engine.place_order(symbol, side, amount, type='market') # Market for ensure fill for now
                if order:
                    self.ledger.record_trade({
                        'symbol': symbol, 'side': side, 'amount': amount, 
                        'price': order.get('average', signal['price']),
                        'cost': order.get('cost', 0),
                        'strategy_data': signal['reason']
                    })
            
            self.current_state = State.WAIT_CANDLE_CLOSE # Done for this tick
            self._sleep_until_next_period()

    def _sleep_until_next_period(self):
        # Placeholder sleep
        time.sleep(10)
