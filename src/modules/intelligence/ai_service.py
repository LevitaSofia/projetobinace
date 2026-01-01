import os
import logging
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
from src.modules.intelligence.prompts import SANDRA_SYSTEM_PROMPT, ANALYSIS_TEMPLATE

load_dotenv()

class AIService:
    def __init__(self):
        self.logger = logging.getLogger("AIService")
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.enabled = False
        self.client = None
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4')

        if not self.api_key or self.api_key.startswith("sk-xxxx"):
            self.logger.warning("⚠️ OpenAI API Key not found. AI features disabled.")
        else:
            try:
                self.client = OpenAI(api_key=self.api_key)
                self.enabled = True
                self.logger.info("🧠 AI Service (Sandra) Initialized.")
            except Exception as e:
                self.logger.error(f"❌ Failed to initialize OpenAI: {e}")

    def analyze_trade(self, symbol, market_data):
        """
        Asks AI to analyze a potential trade.
        market_data: dict with rsi, price, volatility, trend, cost_pct
        """
        if not self.enabled:
            return None

        prompt = ANALYSIS_TEMPLATE.format(
            symbol=symbol,
            price=market_data.get('price'),
            rsi=market_data.get('rsi'),
            volatility=market_data.get('volatility', 0.0),
            trend=market_data.get('trend', 'Neutral'),
            cost_pct=market_data.get('cost_pct', 0.0)
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SANDRA_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={ "type": "json_object" }
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            self.logger.error(f"🧠 AI Analysis Failed: {e}")
            return None
