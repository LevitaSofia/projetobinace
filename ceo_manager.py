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


def calcular_sl_dinamico(atr_value, adx_value=None, sentiment="NEUTRO"):
    """
    🧠 INTELIGÊNCIA ARTIFICIAL: Stop Loss Dinâmico baseado em ATR e Tendência
    
    Args:
        atr_value (float): Average True Range (volatilidade)
        adx_value (float): Average Directional Index (força da tendência)
        sentiment (str): Sentimento do mercado (BULL/BEAR/NEUTRO)
        
    Returns:
        float: Stop Loss em % (negativo)
        
    Lógica:
    - Mercado volátil (ATR alto) = SL mais largo (para não ser stopped prematuramente)
    - Mercado calmo (ATR baixo) = SL apertado (proteção máxima)
    - Tendência forte contra posição (ADX alto) = SL apertado (sai rápido)
    - Mercado BEAR = SL apertado (preserva capital)
    """
    try:
        if not atr_value or atr_value <= 0:
            # Sem dados de ATR, usa SL conservador
            return -1.8
        
        # Base: 2.0x o ATR (método padrão de trading profissional)
        sl_base = 2.0 * atr_value
        
        # Ajuste por ADX (força da tendência)
        if adx_value and adx_value > 40:
            # Tendência muito forte = reduz SL em 20% (sai mais rápido se contra a tendência)
            sl_base *= 0.8
        elif adx_value and adx_value < 20:
            # Mercado lateral = aumenta SL em 15% (dá mais espaço)
            sl_base *= 1.15
        
        # Ajuste por sentimento de mercado
        if sentiment == "BEAR":
            # Mercado em baixa = reduz SL em 25% (proteção máxima)
            sl_base *= 0.75
        elif sentiment == "BULL":
            # Mercado em alta = aumenta SL em 20% (dá mais espaço)
            sl_base *= 1.2
        
        # Limites de segurança
        sl_pct = max(min(sl_base, 3.0), 1.2)  # Entre 1.2% e 3.0%
        
        return -sl_pct  # Retorna negativo (convenção do sistema)
        
    except Exception as e:
        print(f"⚠️ Erro calcular_sl_dinamico: {e}")
        return -1.8  # Fallback conservador


def calcular_tp_dinamico(sl_value, adx_value=None, rsi_value=None, sentiment="NEUTRO"):
    """
    🧠 INTELIGÊNCIA ARTIFICIAL: Take Profit Dinâmico baseado em Risco/Recompensa
    
    Args:
        sl_value (float): Stop Loss atual (negativo)
        adx_value (float): Average Directional Index
        rsi_value (float): RSI atual
        sentiment (str): Sentimento do mercado
        
    Returns:
        float: Take Profit em % (positivo)
        
    Lógica:
    - SEMPRE garante R:R mínimo de 1.5:1 (recompensa > risco)
    - Tendência forte (ADX alto) = TP menor (realiza rápido)
    - RSI extremo (< 20) = TP maior (pega o rally completo)
    - Mercado BULL = TP maior (aproveita momentum)
    """
    try:
        sl_abs = abs(sl_value)  # Converte para positivo
        
        # Base: 2.0x o risco (R:R de 2:1)
        tp_base = sl_abs * 2.0
        
        # Ajuste por ADX (força da tendência)
        if adx_value and adx_value > 40:
            # Tendência forte = reduz TP em 20% (realiza antes da reversão)
            tp_base *= 0.8
        elif adx_value and adx_value < 20:
            # Lateral = aumenta TP em 25% (busca movimento maior)
            tp_base *= 1.25
        
        # Ajuste por RSI (sobrevendido extremo)
        if rsi_value and rsi_value < 20:
            # RSI < 20 = mercado despencou, aumenta TP em 40% (pega bounce forte)
            tp_base *= 1.4
        elif rsi_value and rsi_value < 25:
            # RSI < 25 = muito vendido, aumenta TP em 20%
            tp_base *= 1.2
        
        # Ajuste por sentimento
        if sentiment == "BULL":
            # Mercado subindo = aumenta TP em 30% (aproveita momentum)
            tp_base *= 1.3
        elif sentiment == "BEAR":
            # Mercado caindo = reduz TP em 20% (realiza rápido)
            tp_base *= 0.8
        
        # Limites de segurança
        tp_pct = max(min(tp_base, 8.0), 2.5)  # Entre 2.5% e 8.0%
        
        # Garantia: SEMPRE R:R >= 1.5:1 (considerando 0.6% de taxas)
        min_tp = (sl_abs + 0.6) * 1.5
        if tp_pct < min_tp:
            tp_pct = min_tp
        
        return tp_pct
        
    except Exception as e:
        print(f"⚠️ Erro calcular_tp_dinamico: {e}")
        return 4.0  # Fallback: 4% (conservador)


def calcular_tamanho_aposta(rsi_value, volume_ratio, sentiment, atr_value, base_bet=11.0):
    """
    🧠 INTELIGÊNCIA ARTIFICIAL: Tamanho da Aposta baseado em Confluência de Sinais
    
    Args:
        rsi_value (float): RSI atual
        volume_ratio (float): Volume atual / média (ex: 1.5 = 50% acima da média)
        sentiment (str): Sentimento do mercado
        atr_value (float): ATR (volatilidade)
        base_bet (float): Aposta base em USD
        
    Returns:
        float: Valor da aposta em USD
        
    Lógica:
    - Quanto mais confluências, maior a aposta
    - RSI < 20 + Volume alto + BEAR = OPORTUNIDADE MÁXIMA
    - ATR alto = reduz aposta (mercado volátil = mais risco)
    """
    try:
        pontos = 0  # Sistema de pontuação
        
        # Pontos por RSI (sobrevendido)
        if rsi_value < 20:
            pontos += 3  # Extremamente sobrevendido
        elif rsi_value < 25:
            pontos += 2
        elif rsi_value < 30:
            pontos += 1
        
        # Pontos por Volume (confirmação)
        if volume_ratio > 1.5:
            pontos += 2  # Volume muito alto
        elif volume_ratio > 1.2:
            pontos += 1
        
        # Pontos por Sentimento (oportunidade contra-tendência)
        if sentiment == "BEAR":
            pontos += 2  # Comprar no pânico
        elif sentiment == "NEUTRO":
            pontos += 1
        
        # Penalidade por volatilidade extrema
        if atr_value > 3.0:
            pontos -= 1  # ATR muito alto = mais risco
        
        # Decisão de aposta
        if pontos >= 6:
            # Confluência máxima (RSI < 20 + Volume + BEAR)
            return base_bet * 3.0  # $33
        elif pontos >= 4:
            # Confluência forte (RSI < 25 + Volume)
            return base_bet * 2.0  # $22
        elif pontos >= 2:
            # Confluência média (RSI < 30)
            return base_bet  # $11
        else:
            # Sinal fraco
            return 0.0  # Não aposta
            
    except Exception as e:
        print(f"⚠️ Erro calcular_tamanho_aposta: {e}")
        return base_bet


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
