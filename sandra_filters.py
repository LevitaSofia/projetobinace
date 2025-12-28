"""
sandra_filters.py - Sandra 3.1: Majors First + Filtros Extremos

Sistema de filtros completo implementando a filosofia "majors first":
- TIER A (BTC/ETH/SOL/BNB) tem prioridade absoluta
- TIER B só em casos extremos (RSI 20-24, regime BULL, edge alto)
- RSI multi-timeframe obrigatório (5m + 15m)
- Edge líquido verificado ANTES de comprar
- Regime BTC obrigatório para TIER B
"""

import pandas as pd
import pandas_ta as ta


# TIER System
TIER_A_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']


def is_tier_a(symbol):
    """Verifica se símbolo é TIER A (major)."""
    return symbol in TIER_A_SYMBOLS


def calculate_rsi_multitimeframe(exchange, symbol):
    """
    Calcula RSI em múltiplos timeframes (1h e 4h).
    
    Returns:
        dict: {'rsi_1h': float, 'rsi_4h': float, 'rsi_5m': float, 'rsi_15m': float, 'success': bool}
    """
    try:
        # RSI 1h (timeframe principal)
        klines_1h = exchange.fetch_ohlcv(symbol, '1h', limit=50)
        if not klines_1h or len(klines_1h) < 14:
            return {'success': False, 'error': 'Dados 1h insuficientes'}
        
        df_1h = pd.DataFrame(klines_1h, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        rsi_1h = float(ta.rsi(df_1h['close'], length=14).iloc[-1])
        
        # RSI 4h (confirmação maior)
        klines_4h = exchange.fetch_ohlcv(symbol, '4h', limit=50)
        if not klines_4h or len(klines_4h) < 14:
            return {'success': False, 'error': 'Dados 4h insuficientes'}
        
        df_4h = pd.DataFrame(klines_4h, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        rsi_4h = float(ta.rsi(df_4h['close'], length=14).iloc[-1])
        
        # Mantém 5m e 15m para compatibilidade (valores iguais a 1h)
        return {
            'success': True,
            'rsi_1h': rsi_1h,
            'rsi_4h': rsi_4h,
            'rsi_5m': rsi_1h,  # Compatibilidade
            'rsi_15m': rsi_4h  # Compatibilidade
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


def calculate_btc_regime(exchange):
    """
    Calcula regime BTC (EMA50 vs EMA200 em 1h).
    
    Returns:
        dict: {'regime': 'BULL'|'BEAR'|'NEUTRAL', 'ema50': float, 'ema200': float}
    """
    try:
        klines = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        if not klines or len(klines) < 200:
            return {'regime': 'UNKNOWN', 'error': 'Dados insuficientes'}
        
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['EMA50'] = ta.ema(df['close'], length=50)
        df['EMA200'] = ta.ema(df['close'], length=200)
        
        ema50 = float(df['EMA50'].iloc[-1])
        ema200 = float(df['EMA200'].iloc[-1])
        
        if ema50 > ema200:
            regime = 'BULL'
        elif ema50 < ema200:
            regime = 'BEAR'
        else:
            regime = 'NEUTRAL'
        
        return {
            'regime': regime,
            'ema50': ema50,
            'ema200': ema200,
            'success': True
        }
    
    except Exception as e:
        return {'regime': 'UNKNOWN', 'error': str(e), 'success': False}


def calculate_edge_liquido(symbol, position_size, tp_pct, exchange):
    """
    Calcula edge líquido (lucro esperado - custos totais).
    
    Args:
        symbol: Par (ex: 'BTC/USDT')
        position_size: Tamanho em USDT
        tp_pct: Take profit %
        exchange: Instância ccxt
    
    Returns:
        dict: {'edge_liquido': float, 'costs_total': float, 'spread_bps': float}
    """
    try:
        # Taxas Binance Spot
        FEE_RATE = 0.001  # 0.1%
        fee_compra = position_size * FEE_RATE
        fee_venda = position_size * FEE_RATE
        
        # Spread do orderbook
        try:
            depth = exchange.fetch_order_book(symbol, limit=5)
            bid = depth['bids'][0][0]
            ask = depth['asks'][0][0]
            spread_pct = ((ask - bid) / bid) * 100
            spread_bps = spread_pct * 100
            spread_cost = position_size * (spread_pct / 100)
        except:
            # Fallback: spread médio estimado
            spread_bps = 10.0 if is_tier_a(symbol) else 15.0
            spread_cost = position_size * (spread_bps / 10000)
        
        # Slippage estimado
        slippage_pct = 0.10 if is_tier_a(symbol) else 0.15
        slippage_cost = position_size * (slippage_pct / 100)
        
        # Custos totais
        costs_total_usd = fee_compra + fee_venda + spread_cost + slippage_cost
        costs_total_pct = (costs_total_usd / position_size) * 100
        
        # Edge líquido
        edge_liquido_pct = tp_pct - costs_total_pct
        
        return {
            'success': True,
            'edge_liquido': edge_liquido_pct,
            'costs_total': costs_total_pct,
            'spread_bps': spread_bps,
            'breakdown': {
                'fee_compra': fee_compra,
                'fee_venda': fee_venda,
                'spread': spread_cost,
                'slippage': slippage_cost
            }
        }
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


def check_tier_a_entry(symbol, rsi_5m, rsi_15m, price, bb_lower, regime_btc, edge_liquido):
    """
    Verifica se TIER A (major) pode entrar.
    
    Critérios:
    - RSI 5m ≤ 42
    - RSI 15m ≤ 50 (confirma que não é só ruído)
    - Preço próximo de BB.low
    - Edge líquido ≥ 0.5%
    - Se regime BEAR: critérios mais duros
    
    Returns:
        dict: {'approved': bool, 'reasons': list, 'warnings': list}
    """
    reasons = []
    warnings = []
    approved = True
    
    # RSI 5m
    RSI_5M_MAX = 30 if regime_btc == 'BEAR' else 42
    if rsi_5m > RSI_5M_MAX:
        approved = False
        reasons.append(f"RSI 5m {rsi_5m:.1f} > {RSI_5M_MAX}")
    else:
        reasons.append(f"✅ RSI 5m {rsi_5m:.1f} ≤ {RSI_5M_MAX}")
    
    # RSI 15m (confirma)
    RSI_15M_MAX = 38 if regime_btc == 'BEAR' else 50
    if rsi_15m > RSI_15M_MAX:
        approved = False
        reasons.append(f"RSI 15m {rsi_15m:.1f} > {RSI_15M_MAX} (sem confirmação)")
    else:
        reasons.append(f"✅ RSI 15m {rsi_15m:.1f} ≤ {RSI_15M_MAX}")
    
    # Banda de Bollinger
    if bb_lower > 0:
        dist_bb = ((price - bb_lower) / bb_lower) * 100
        if dist_bb > 2.0:
            warnings.append(f"⚠️ Distância BB.low: {dist_bb:.2f}% (longe)")
        else:
            reasons.append(f"✅ Preço próximo BB.low ({dist_bb:.2f}%)")
    
    # Edge líquido
    EDGE_MIN = 0.5
    if edge_liquido < EDGE_MIN:
        approved = False
        reasons.append(f"Edge {edge_liquido:.2f}% < {EDGE_MIN}% (não cobre custos)")
    else:
        reasons.append(f"✅ Edge líquido {edge_liquido:.2f}% ≥ {EDGE_MIN}%")
    
    # Regime BTC (aviso em BEAR, mas não bloqueia TIER A)
    if regime_btc == 'BEAR':
        warnings.append(f"⚠️ Regime BTC: BEAR (risco maior)")
    elif regime_btc == 'BULL':
        reasons.append(f"✅ Regime BTC: BULL")
    
    return {
        'approved': approved,
        'reasons': reasons,
        'warnings': warnings
    }


def check_tier_b_entry(symbol, rsi_5m, rsi_15m, price, bb_lower, regime_btc, 
                       edge_liquido, volume_24h, spread_bps):
    """
    Verifica se TIER B (emergente) pode entrar.
    
    Critérios EXTREMOS:
    - Regime BTC = BULL (obrigatório)
    - RSI 5m ≤ 24 (muito baixo)
    - RSI 15m ≤ 32 (confirma)
    - Preço ≤ BB.low * 1.01 (colado)
    - Edge líquido ≥ 1.2% (muito maior que TIER A)
    - Volume 24h alto
    - Spread bom
    
    Returns:
        dict: {'approved': bool, 'reasons': list, 'violations': list}
    """
    reasons = []
    violations = []
    approved = True
    
    # 1. Regime BTC (obrigatório BULL)
    if regime_btc != 'BULL':
        approved = False
        violations.append(f"🚫 Regime BTC: {regime_btc} (TIER B exige BULL)")
    else:
        reasons.append(f"✅ Regime BTC: BULL")
    
    # 2. RSI 5m (extremo)
    RSI_5M_MAX = 24
    if rsi_5m > RSI_5M_MAX:
        approved = False
        violations.append(f"🚫 RSI 5m {rsi_5m:.1f} > {RSI_5M_MAX} (não extremo o suficiente)")
    else:
        reasons.append(f"✅ RSI 5m {rsi_5m:.1f} ≤ {RSI_5M_MAX} (EXTREMO)")
    
    # 3. RSI 15m (confirma)
    RSI_15M_MAX = 32
    if rsi_15m > RSI_15M_MAX:
        approved = False
        violations.append(f"🚫 RSI 15m {rsi_15m:.1f} > {RSI_15M_MAX} (sem confirmação)")
    else:
        reasons.append(f"✅ RSI 15m {rsi_15m:.1f} ≤ {RSI_15M_MAX}")
    
    # 4. Preço colado em BB.low
    if bb_lower > 0:
        dist_bb = ((price - bb_lower) / bb_lower) * 100
        if dist_bb > 1.0:
            approved = False
            violations.append(f"🚫 Distância BB.low: {dist_bb:.2f}% > 1% (não colado)")
        else:
            reasons.append(f"✅ Preço colado BB.low ({dist_bb:.2f}%)")
    
    # 5. Edge líquido (rigoroso)
    EDGE_MIN = 1.2
    if edge_liquido < EDGE_MIN:
        approved = False
        violations.append(f"🚫 Edge {edge_liquido:.2f}% < {EDGE_MIN}% (TIER B exige mais)")
    else:
        reasons.append(f"✅ Edge líquido {edge_liquido:.2f}% ≥ {EDGE_MIN}%")
    
    # 6. Volume 24h
    VOL_MIN = 5_000_000  # $5M (mais alto que $100k de antes)
    if volume_24h < VOL_MIN:
        approved = False
        violations.append(f"🚫 Volume ${volume_24h:,.0f} < ${VOL_MIN:,}")
    else:
        reasons.append(f"✅ Volume ${volume_24h:,.0f} ≥ ${VOL_MIN:,}")
    
    # 7. Spread
    SPREAD_MAX = 12  # bps (mais rígido que antes)
    if spread_bps > SPREAD_MAX:
        approved = False
        violations.append(f"🚫 Spread {spread_bps:.1f} bps > {SPREAD_MAX} bps")
    else:
        reasons.append(f"✅ Spread {spread_bps:.1f} bps ≤ {SPREAD_MAX} bps")
    
    return {
        'approved': approved,
        'reasons': reasons,
        'violations': violations
    }


def check_reentry_guard(symbol, strategy, current_time):
    """
    Verifica ReEntryGuard (90 minutos após QUALQUER venda).
    
    Libera antes dos 90min apenas se:
    - Novo fundo real: preço atual ≤ (preço venda * 0.992)
    - OU RSI reset: RSI 5m ≤ 20 E RSI 15m ≤ 25
    
    Returns:
        dict: {'blocked': bool, 'reason': str, 'time_remaining_min': float}
    """
    COOLDOWN_SECONDS = 90 * 60  # 90 minutos (mais rigoroso que 60min anterior)
    
    # Verifica se houve venda recente
    last_sell_times = strategy.get('last_sell_time', {})
    
    if symbol not in last_sell_times:
        return {'blocked': False, 'reason': 'Sem venda recente'}
    
    last_sell_time = last_sell_times[symbol]
    time_since_sell = current_time - last_sell_time
    
    if time_since_sell >= COOLDOWN_SECONDS:
        return {'blocked': False, 'reason': 'Cooldown expirado'}
    
    # Cooldown ainda ativo
    time_remaining_min = (COOLDOWN_SECONDS - time_since_sell) / 60
    
    # TODO: Verificar se houve novo fundo ou RSI reset
    # (requer preço da venda e RSI atual, não disponíveis aqui)
    # Por enquanto, bloqueia sempre dentro do cooldown
    
    return {
        'blocked': True,
        'reason': f'ReEntryGuard ativo: {time_remaining_min:.0f} min restantes',
        'time_remaining_min': time_remaining_min
    }
