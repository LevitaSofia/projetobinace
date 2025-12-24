"""scalper_blindado.py - Cérebro Inteligente (Elite vs Degen).

Regras:
- Moedas ELITE (BTC/ETH/BNB/SOL) compram mais fácil (RSI < 35)
- Altcoins/DEGEN só entram no fundo (RSI < 28)
- Não há bloqueio por "baixa volatilidade" (ATR) para não perder fundos.
"""

import pandas as pd
import pandas_ta as ta


MOEDAS_FORTES = {'BTC', 'ETH', 'BNB', 'SOL'}


def analisar_sinal_hibrido(candles_raw, symbol_name="UNKNOWN"):
    """Analisa compra com critérios diferentes para moedas Fortes vs Normais.

    Args:
        candles_raw: Lista de listas [[time, open, high, low, close, vol], ...]
        symbol_name: Ex: "BTC/USDT" (usado para decidir elite vs degen)

    Returns:
        (Aprovado: bool, Motivo: str, Dados: dict)
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

        if eh_forte:
            config = {
                'RSI_GATILHO': 35,
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

        # ATR 14 (telemetria)
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

        dados = {
            'price': price,
            'rsi': rsi,
            'adx': adx,
            'atr': atr,
            'bb_lower': bb_lower,
            'bb_upper': bb_upper,
            'vol_now': float(atual['volume']) if not pd.isna(atual['volume']) else 0.0,
            'tier': config.get('TIPO'),
        }

        if pd.isna(price) or pd.isna(rsi):
            return False, "Indicadores calculados como NaN", dados

        if rsi >= config['RSI_GATILHO']:
            return False, f"RSI {rsi:.1f} >= {config['RSI_GATILHO']} (Regra {config['TIPO']})", dados

        if adx > config['ADX_MAXIMO']:
            return False, f"Tendência Extrema (ADX {adx:.1f} > {config['ADX_MAXIMO']})", dados

        return True, f"ENTRADA {config['TIPO']} APROVADA", dados

    except Exception as e:
        print(f"Erro Scalper: {e}")
        return False, f"Erro: {e}", {}
