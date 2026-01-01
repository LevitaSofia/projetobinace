import sys
import os
import random

# Adjust path to find the module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from src.modules.intelligence.fibonacci_analyzer import calculate_fib_levels
except ImportError as e:
    print(f"❌ Failed to import fibonacci_analyzer: {e}")
    sys.exit(1)

# Generate synthetic uptrend data (Swing Low -> Swing High -> Retracement)
candles = []
price = 100.0
# 1. Rise from 100 to 200
for i in range(120): # Increased to ensure > 100 total candles
    price += 0.8 + random.uniform(-0.2, 0.2)
    candles.append([0, 0, price + 1, price - 1, price, 1000])

# 2. Retrace to 0.618 level (from 100 to 200, diff=100. 0.618 retracement = 200 - 61.8 = 138.2)
target = 138.2
current = candles[-1][4]
steps = 30
step_size = (current - target) / steps

for i in range(steps):
    current -= step_size
    candles.append([0, 0, current + 1, current - 1, current, 1000])

# Test
print(f"📉 Testing Retracement Analysis (Expected touch at ~138.2)...")
result = calculate_fib_levels(candles, lookback=100)

if result['success']:
    print("✅ Calculation Successful")
    print(f"   Structure: {result['trend']}")
    print(f"   Swing High: {result['swing_high']:.2f}")
    print(f"   Swing Low: {result['swing_low']:.2f}")
    print(f"   Levels: {result['levels']}")
    print(f"   Current Price: {result['current_price']:.2f}")
    print(f"   Touching: {result['touching_level']}")
    print(f"   Score: {result['confluence_score']}")
    
    if result['touching_level'] == '0.618':
        print("✅ SNIPER CONFIRMED: Touching 0.618")
    else:
        print(f"⚠️ Not touching 0.618 (Found: {result['touching_level']})")
else:
    print(f"❌ Error: {result['error']}")
