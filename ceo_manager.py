import requests


def get_market_sentiment():
    """Consulta o Fear & Greed Index (Alternative.me)."""
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = response.json()

        fng_value = int(data['data'][0]['value'])

        if fng_value >= 70:
            return "BULL", fng_value
        if fng_value <= 25:
            return "BEAR", fng_value
        return "NEUTRO", fng_value
    except Exception as e:
        print(f"Erro no CEO (Sentimento): {e}")
        return "NEUTRO", 50


def calculate_dynamic_strategy(sentiment, fng_value):
    """Define a agressividade da Sandra com base no mercado."""
    _ = fng_value
    config = {
        "ENTRY_RSI": 35,
        "STOP_BASE": -3.0,
        "ENTRY_TOL": 0.01,
        "MODE": "MODERADO",
    }

    if sentiment == "BULL":
        config["ENTRY_RSI"] = 40
        config["STOP_BASE"] = -4.5
        config["ENTRY_TOL"] = 0.015
        config["MODE"] = "AGRESSIVO"
    elif sentiment == "BEAR":
        config["ENTRY_RSI"] = 28
        config["STOP_BASE"] = -2.0
        config["ENTRY_TOL"] = 0.005
        config["MODE"] = "DEFENSIVO"

    return config
