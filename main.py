import sys
import os
import signal
from dotenv import load_dotenv

# Ensure the project root is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.infrastructure.logging_setup import setup_logging
from src.bot.state_machine import BotStateMachine

def main():
    load_dotenv()
    logger = setup_logging()
    
    logger.info("🚀 Starting Sandra 4.0 (Intelligent Agent)...")
    
    # Configuration (could be moved to config file)
    symbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT']
    timeframe = '1h'
    
    bot = BotStateMachine(symbols, timeframe)
    
    # Graceful Shutdown
    def signal_handler(sig, frame):
        logger.info("🛑 Received Shutdown Signal. Exiting...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    bot.run()

if __name__ == "__main__":
    main()
