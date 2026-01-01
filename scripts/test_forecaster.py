from src.modules.intelligence.forecaster import MarketForecaster

def test_forecaster():
    f = MarketForecaster()
    report = f.generate_prediction_report(
        symbol='BTC/USDT',
        current_price=88000.0,
        atr=500.0,
        rsi=55.0,
        ml_prob=45.0,
        fib_levels={'0.618': 87000.0}
    )
    print(report)

if __name__ == "__main__":
    test_forecaster()
