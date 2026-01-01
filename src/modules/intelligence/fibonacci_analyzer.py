"""
fibonacci_analyzer.py - Análise de Estrutura de Mercado e Fibonacci

Este módulo identifica Swing Highs e Lows recentes para traçar retrações de Fibonacci.
É o "olho estrutural" da Sandra 3.1.
"""

import pandas as pd
import numpy as np

def calculate_fib_levels(candles_raw, lookback=150):
    """
    Identifica a estrutura macro (Swing High/Low) e calcula retrações.
    
    Args:
        candles_raw: Lista de candles (OHLCV).
        lookback: Quantos candles olhar para trás para achar o topo/fundo relevante.
        
    Returns:
        dict: Níveis de Fibonacci e status do preço atual.
            {
                '0.618': float,
                '0.5': float,
                '0.382': float,
                'swing_high': float,
                'swing_low': float,
                'current_price': float,
                'trend': 'UP' or 'DOWN',
                'touching_level': '0.618' or None, # Qual nível está tocando
                'confluence_score': int # 0 a 100
            }
    """
    if not candles_raw or len(candles_raw) < lookback:
        return {'success': False, 'error': 'Dados insuficientes'}

    try:
        df = pd.DataFrame(candles_raw, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['close'] = pd.to_numeric(df['close'])
        
        # Analisa a janela recente (Ex: últimas 150 velas de 5m = 12h de dados)
        current_data = df.tail(lookback)
        
        # Encontrar Swing High (Topo Absoluto da janela)
        swing_high_idx = current_data['high'].idxmax()
        swing_high_val = current_data.loc[swing_high_idx, 'high']
        
        # Encontrar Swing Low (Fundo Absoluto da janela)
        swing_low_idx = current_data['low'].idxmin()
        swing_low_val = current_data.loc[swing_low_idx, 'low']
        
        current_price = df['close'].iloc[-1]
        
        # Determinar a "Pernada" (Impulso)
        # Se o Topo veio depois do Fundo -> Tendência de Alta (Estamos corrigindo) 
        # Fibonacci é traçado do Fundo para o Topo
        is_uptrend = swing_high_idx > swing_low_idx 
        
        levels = {}
        
        if is_uptrend:
            # Alta: Retração mede a queda (correção)
            diff = swing_high_val - swing_low_val
            levels['0.236'] = swing_high_val - (diff * 0.236)
            levels['0.382'] = swing_high_val - (diff * 0.382)
            levels['0.5'] = swing_high_val - (diff * 0.5)
            levels['0.618'] = swing_high_val - (diff * 0.618) # Golden Pocket
            levels['0.786'] = swing_high_val - (diff * 0.786)
        else:
            # Baixa: Retração mede o repique (subida)
            # Fibo traçado do Topo para o Fundo
            diff = swing_high_val - swing_low_val
            levels['0.236'] = swing_low_val + (diff * 0.236)
            levels['0.382'] = swing_low_val + (diff * 0.382)
            levels['0.5'] = swing_low_val + (diff * 0.5)
            levels['0.618'] = swing_low_val + (diff * 0.618)
            levels['0.786'] = swing_low_val + (diff * 0.786)
            
        # Verificar Proximidade (Buffer de 0.3%)
        touching = None
        min_dist = float('inf')
        
        buffer_pct = 0.003 # 0.3%
        
        for level_name, level_price in levels.items():
            dist = abs(current_price - level_price) / current_price
            if dist <= buffer_pct:
                touching = level_name
                # Se estiver tocando em mais de um (impossível matematicamente, mas ok), pega o mais próximo
                if dist < min_dist:
                    min_dist = dist
                    touching = level_name
        
        # Score de Confluência
        # Se tocar no 0.618 ou 0.5 ou 0.786 ganha pontos
        score = 0
        if touching == '0.618': score = 100
        elif touching == '0.5': score = 80
        elif touching == '0.786': score = 90
        elif touching == '0.382': score = 40
        
        return {
            'success': True,
            'trend': 'UP' if is_uptrend else 'DOWN',
            'swing_high': swing_high_val,
            'swing_low': swing_low_val,
            'levels': levels,
            'current_price': current_price,
            'touching_level': touching,
            'confluence_score': score
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    # Teste rápido se rodar direto
    print("Módulo de Fibonacci carregado. Importe para usar.")
