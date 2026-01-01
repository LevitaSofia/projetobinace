"""scalper_blindado.py - Cérebro Inteligente (Elite vs Degen).

Regras:
- Moedas ELITE (BTC/ETH/BNB/SOL) compram mais fácil (RSI < 35)
- Altcoins/DEGEN só entram no fundo (RSI < 28)
- Retorna ATR, ADX, Volume ratio para IA tomar decisões inteligentes
"""

import pandas as pd
import pandas_ta as ta
import os
import sys

# sys.path hack removido após reorganização


try:
    from src.modules.intelligence.fibonacci_analyzer import calculate_fib_levels
    from src.modules.intelligence.ml_predictor import predictor as ml_brain
except ImportError:
    # Fallback silencioso se o arquivo não existir ainda
    def calculate_fib_levels(x, **k): return {'success': False}
    ml_brain = None

MOEDAS_FORTES = {'BTC', 'ETH', 'BNB', 'SOL'}


def analisar_sinal_hibrido(candles_raw, symbol_name="UNKNOWN"):
    """Analisa compra com critérios diferentes para moedas Fortes vs Normais.

    Args:
        candles_raw: Lista de listas [[time, open, high, low, close, vol], ...]
        symbol_name: Ex: "BTC/USDT" (usado para decidir elite vs degen)

    Returns:
        (Aprovado: bool, Motivo: str, Dados: dict)
        
    Dados incluem:
        - price: Preço atual
        - rsi: RSI atual
        - adx: Força da tendência
        - atr: Volatilidade (usado para SL dinâmico)
        - atr_pct: ATR em % do preço
        - bb_lower/bb_upper: Bandas de Bollinger
        - vol_now: Volume atual
        - vol_avg: Volume médio
        - vol_ratio: Volume atual / média
        - tier: Classificação da moeda (ELITE ou DEGEN)
    """
    try:
        if not candles_raw or len(candles_raw) < 20:
            return False, "Dados insuficientes", {}

        base = "UNKNOWN"
        try:
            base = str(symbol_name).split('/')[0].upper().strip()
        except Exception:
            base = "UNKNOWN"

        eh_forte = base in MOEDAS_FORTES

        # 🎯 CONFIGURAÇÃO ELITE PERSONALIZADA (INDIVIDUAL)
        # Ajuste fino baseado no histórico de performance
        RSI_THRESHOLDS = {
            'ETH': 37,  # Campeã (87%): Mais flexível
            'SOL': 37,  # Invicta (100%): Mais flexível
            'BTC': 35,  # Referência: Padrão
            'XRP': 32,  # Nova: Conservador
        }
        
        # Pega limite específico ou usa padrão
        rsi_limite_base = RSI_THRESHOLDS.get(base, 28 if not eh_forte else 35)

        if eh_forte:
            config = {
                'RSI_GATILHO': rsi_limite_base,
                'ADX_MAXIMO': 60,
                'TIPO': '👑 ELITE (Forte)',
            }
        else:
            config = {
                'RSI_GATILHO': 28,
                'ADX_MAXIMO': 60,
                'TIPO': '🎰 DEGEN (Arriscada)',
            }

        df = pd.DataFrame(candles_raw, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')

        df['RSI'] = ta.rsi(df['close'], length=14)

        # ADX 14 (robusto)
        try:
            adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
            if adx_df is not None and not adx_df.empty:
                if 'ADX_14' in adx_df.columns:
                    df['ADX'] = adx_df['ADX_14']
                else:
                    df['ADX'] = adx_df.iloc[:, 0]
            else:
                df['ADX'] = 0.0
        except Exception:
            df['ADX'] = 0.0

        # ATR 14 (telemetria) - ESSENCIAL PARA IA
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)

        bb = ta.bbands(df['close'], length=20, std=2.0)
        atual = df.iloc[-1]

        rsi = float(atual['RSI']) if not pd.isna(atual['RSI']) else float('nan')
        adx = float(atual['ADX']) if not pd.isna(atual['ADX']) else 0.0
        atr = float(atual['ATR']) if not pd.isna(atual['ATR']) else 0.0
        price = float(atual['close']) if not pd.isna(atual['close']) else float('nan')

        # Bandas de Bollinger (robusto)
        try:
            if bb is None or bb.empty:
                bb_lower, bb_upper = float('nan'), float('nan')
            else:
                key_lower = 'BBL_20_2.0'
                key_upper = 'BBU_20_2.0'

                if key_lower in bb.columns and key_upper in bb.columns:
                    bb_lower = float(bb[key_lower].iloc[-1])
                    bb_upper = float(bb[key_upper].iloc[-1])
                else:
                    lower_cols = [c for c in bb.columns if str(c).startswith('BBL_')]
                    upper_cols = [c for c in bb.columns if str(c).startswith('BBU_')]

                    if lower_cols:
                        bb_lower = float(bb[lower_cols[0]].iloc[-1])
                    else:
                        bb_lower = float(bb.iloc[-1, 0])

                    if upper_cols:
                        bb_upper = float(bb[upper_cols[0]].iloc[-1])
                    else:
                        bb_upper = float(bb.iloc[-1, 2])
        except Exception:
            bb_lower, bb_upper = float('nan'), float('nan')

        # --- PREPARA COLUNAS PARA ML (Vectorized) ---
        # Renomeia para lowercase para compatibilidade
        if 'RSI' in df.columns: df['rsi'] = df['RSI']
        if 'ADX' in df.columns: df['adx'] = df['ADX']
        if 'ATR' in df.columns: 
            df['atr_pct'] = (df['ATR'] / df['close']) * 100
        else:
            df['atr_pct'] = 0.0
        
        # Volume Ratio (Rolling Mean 20)
        df['vol_avg'] = df['volume'].rolling(window=20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_avg']

        # Bandas para ML (precisamos adicionar ao DF para training)
        if bb is not None and not bb.empty:
            # Tenta achar colunas
            lower_cols = [c for c in bb.columns if str(c).startswith('BBL_')]
            if lower_cols:
                df['bb_lower'] = bb[lower_cols[0]]
                # Distância da banda (feature importante)
                df['dist_from_bb_lower'] = (df['close'] - df['bb_lower']) / df['close']
            else:
                 df['bb_lower'] = 0.0
                 df['dist_from_bb_lower'] = 0.0
        else:
             df['bb_lower'] = 0.0
             df['dist_from_bb_lower'] = 0.0
        
        # Preenche NaNs gerados pelo rolling (início do DF)
        df.fillna(0, inplace=True)


        # 🧠 INTELIGÊNCIA: Calcula volume ratio (para aposta dinâmica)
        vol_now = float(atual['volume']) if not pd.isna(atual['volume']) else 0.0
        vol_avg = float(df['volume'].tail(20).mean()) if len(df) >= 20 else vol_now
        vol_ratio = vol_now / vol_avg if vol_avg > 0 else 1.0
        
        # 🧠 INTELIGÊNCIA: ATR em % do preço (para SL dinâmico)
        atr_pct = (atr / price * 100) if price > 0 and atr > 0 else 0.0
        
        # 🧠 TENDÊNCIA: EMA 50 vs EMA 200 (mercado de alta ou baixa?)
        try:
            df['EMA50'] = ta.ema(df['close'], length=50)
            df['EMA200'] = ta.ema(df['close'], length=200)
            ema50 = float(df['EMA50'].iloc[-1]) if not pd.isna(df['EMA50'].iloc[-1]) else price
            ema200 = float(df['EMA200'].iloc[-1]) if not pd.isna(df['EMA200'].iloc[-1]) else price
            tendencia_alta = ema50 > ema200  # True = mercado de alta
        except Exception:
            ema50 = price
            ema200 = price
            tendencia_alta = True  # Default: otimista

        dados = {
            'price': price,
            'rsi': rsi,
            'adx': adx,
            'atr': atr,
            'atr_pct': atr_pct,  # Novo: ATR em %
            'bb_lower': bb_lower,
            'bb_upper': bb_upper,
            'vol_now': vol_now,
            'vol_avg': vol_avg,  # Novo: Volume médio
            'vol_ratio': vol_ratio,  # Novo: Ratio do volume
            'tier': config.get('TIPO'),
            'ema50': ema50,  # 🆕 EMA 50
            'ema200': ema200,  # 🆕 EMA 200
            'tendencia_alta': tendencia_alta,  # 🆕 Mercado em alta?
        }
        
        # 🧠 INTELIGÊNCIA FIBONACCI (NOVO)
        # Calcula níveis de retração estrutural
        fib_data = calculate_fib_levels(candles_raw, lookback=100)
        dados['fibonacci'] = fib_data
        
        # Adiciona flag de confluência
        fib_score = fib_data.get('confluence_score', 0)
        dados['fib_confluence'] = fib_score >= 80 # Só considera confluência se tocar em 0.618 ou 0.5

        # 🤖 MACHINE LEARNING (SUPER CÉREBRO)
        ml_prob = 50.0
        if ml_brain:
            # Treina se necessário (primeira vez)
            if not ml_brain.is_trained:
                print("🧠 Treinando Cérebro ML em background...")
                # Cria DataFrame completo para treino
                ml_brain.train_model(df)
            
            # Prepara indicadores atuais para previsão
            indicators_ml = {
                'rsi': rsi,
                'adx': adx,
                'atr_pct': atr_pct,
                'vol_ratio': vol_ratio,
                'dist_from_bb_lower': (price - bb_lower) / price if bb_lower and price else 0.0
            }
            ml_prob = ml_brain.predict_score(indicators_ml)
            
        dados['ml_prob'] = ml_prob


        if pd.isna(price) or pd.isna(rsi):
            return False, "Indicadores calculados como NaN", dados

        if pd.isna(price) or pd.isna(rsi):
            return False, "Indicadores calculados como NaN", dados

        # REGRA MESTRA:
        # 1. Se tiver Confluência FIBO (Preço no 0.618), aceita RSI até 35 (mais flexível)
        # 2. Se não tiver Fibo, segue regra rígida (RSI < 28 ou 35 dependendo da moeda)
        
        rsi_limite = config['RSI_GATILHO']
        tem_fibo = dados.get('fib_confluence', False)
        
        if tem_fibo:
            rsi_limite += 5 # Dá um bônus de 5 pontos no RSI se tiver suporte matemático
            
        if rsi >= rsi_limite:
            if tem_fibo:
                return False, f"RSI {rsi:.1f} alto mesmo c/ Fibo (Limite {rsi_limite})", dados
            return False, f"RSI {rsi:.1f} >= {rsi_limite} (Sem Fibo)", dados

        if adx > config['ADX_MAXIMO']:
            return False, f"Tendência Extrema (ADX {adx:.1f} > {config['ADX_MAXIMO']})", dados
        
        # 🛡️ FILTRO 3: NÃO COMPRAR EM QUEDA LIVRE (EMA 50 abaixo de EMA 200)
        # Exceção: moedas ELITE podem comprar em qualquer condição (recuperam rápido)
        if not eh_forte and not tendencia_alta:
            return False, f"⚠️ TENDÊNCIA DE BAIXA (EMA50 < EMA200) - Aguardando reversão", dados

        # 🛡️ FILTRO 4: MACHINE LEARNING CHECK
        # Se ML disser que é furada (Prob < 40%), bloqueia mesmo com RSI bonito
        if ml_prob < 40.0:
            return False, f"⛔ ML REJEITOU: Probabilidade Baixa ({ml_prob:.1f}%)", dados

        msg_aprovacao = f"ENTRADA {config['TIPO']} APROVADA"
        if tem_fibo:
             msg_aprovacao += " 🎯 (SNIPER FIBO 0.618)"
        
        if ml_prob > 80.0:
            msg_aprovacao += f" 💎 (ML DIAMOND {ml_prob:.0f}%)"
        else:
            msg_aprovacao += f" 🤖 (ML Score: {ml_prob:.0f}%)"
            
        return True, msg_aprovacao, dados

    except Exception as e:
        print(f"Erro Scalper: {e}")
        return False, f"Erro: {e}", {}
