#!/usr/bin/env python3
"""
🧪 Teste do Sistema de IA Dinâmica
Verifica se todas as funções da IA estão funcionando corretamente.
"""

import sys
sys.path.insert(0, '/home/ubuntu/projetobinace')

import ceo_manager

print("=" * 60)
print("🧠 TESTE DO SISTEMA DE IA DINÂMICA")
print("=" * 60)

# Teste 1: Sentimento de Mercado
print("\n📊 Teste 1: Sentimento de Mercado")
try:
    sentiment, fng_value = ceo_manager.get_market_sentiment()
    print(f"✅ Sentimento: {sentiment} (Fear & Greed: {fng_value})")
except Exception as e:
    print(f"❌ Erro: {e}")

# Teste 2: Stop Loss Dinâmico
print("\n🛑 Teste 2: Stop Loss Dinâmico")
test_cases = [
    {"atr": 2.0, "adx": 45, "sentiment": "BEAR", "desc": "Tendência forte + BEAR"},
    {"atr": 1.0, "adx": 15, "sentiment": "NEUTRO", "desc": "Lateral calmo"},
    {"atr": 3.5, "adx": 25, "sentiment": "BULL", "desc": "Volátil + BULL"},
]

for case in test_cases:
    try:
        sl = ceo_manager.calcular_sl_dinamico(case["atr"], case["adx"], case["sentiment"])
        print(f"✅ {case['desc']}: SL = {sl:.2f}%")
    except Exception as e:
        print(f"❌ Erro: {e}")

# Teste 3: Take Profit Dinâmico
print("\n🎯 Teste 3: Take Profit Dinâmico")
test_cases_tp = [
    {"sl": -1.8, "adx": 45, "rsi": 30, "sentiment": "BEAR", "desc": "Tendência forte + BEAR"},
    {"sl": -1.5, "adx": 15, "rsi": 18, "sentiment": "NEUTRO", "desc": "Lateral + RSI extremo"},
    {"sl": -2.0, "adx": 25, "rsi": 28, "sentiment": "BULL", "desc": "BULL + RSI baixo"},
]

for case in test_cases_tp:
    try:
        tp = ceo_manager.calcular_tp_dinamico(case["sl"], case["adx"], case["rsi"], case["sentiment"])
        rr = abs(tp / case["sl"])
        print(f"✅ {case['desc']}: TP = {tp:.2f}% (R:R = {rr:.2f}:1)")
        
        # Valida R:R mínimo
        if rr < 1.5:
            print(f"   ⚠️  AVISO: R:R abaixo de 1.5:1!")
    except Exception as e:
        print(f"❌ Erro: {e}")

# Teste 4: Tamanho de Aposta Dinâmico
print("\n💰 Teste 4: Tamanho de Aposta Dinâmico")
test_cases_bet = [
    {"rsi": 18, "vol_ratio": 2.0, "sentiment": "BEAR", "atr": 2.0, "desc": "OPORTUNIDADE MÁXIMA"},
    {"rsi": 24, "vol_ratio": 1.5, "sentiment": "NEUTRO", "atr": 1.5, "desc": "FORTE"},
    {"rsi": 29, "vol_ratio": 1.0, "sentiment": "BULL", "atr": 1.0, "desc": "PADRÃO"},
    {"rsi": 35, "vol_ratio": 0.8, "sentiment": "BULL", "atr": 0.5, "desc": "FRACO"},
]

for case in test_cases_bet:
    try:
        aposta = ceo_manager.calcular_tamanho_aposta(
            rsi_value=case["rsi"],
            volume_ratio=case["vol_ratio"],
            sentiment=case["sentiment"],
            atr_value=case["atr"],
            base_bet=11.0
        )
        print(f"✅ {case['desc']}: ${aposta:.0f}")
        print(f"   RSI={case['rsi']} | Vol={case['vol_ratio']:.1f}x | Sentimento={case['sentiment']}")
    except Exception as e:
        print(f"❌ Erro: {e}")

# Teste 5: Integração Completa (Simulação de Trade)
print("\n🚀 Teste 5: Simulação de Trade Completo")
try:
    # Dados simulados de mercado
    rsi = 22
    atr_pct = 2.5
    adx = 30
    vol_ratio = 1.8
    
    sentiment, fng = ceo_manager.get_market_sentiment()
    
    # Calcula tudo
    aposta = ceo_manager.calcular_tamanho_aposta(rsi, vol_ratio, sentiment, atr_pct, 11.0)
    sl = ceo_manager.calcular_sl_dinamico(atr_pct, adx, sentiment)
    tp = ceo_manager.calcular_tp_dinamico(sl, adx, rsi, sentiment)
    rr = abs(tp / sl)
    
    print(f"📊 Cenário de Mercado:")
    print(f"   RSI: {rsi} | ATR: {atr_pct}% | ADX: {adx} | Volume: {vol_ratio:.1f}x")
    print(f"   Sentimento: {sentiment} (F&G: {fng})")
    print(f"\n🧠 Decisões da IA:")
    print(f"   💰 Aposta: ${aposta:.0f}")
    print(f"   🛑 Stop Loss: {sl:.2f}%")
    print(f"   🎯 Take Profit: {tp:.2f}%")
    print(f"   📊 Risco/Recompensa: {rr:.2f}:1")
    
    if aposta > 0 and rr >= 1.5:
        print(f"\n✅ TRADE APROVADO PELA IA!")
    else:
        print(f"\n⚠️  Trade rejeitado (aposta={aposta}, R:R={rr:.2f})")
        
except Exception as e:
    print(f"❌ Erro na simulação: {e}")

print("\n" + "=" * 60)
print("🎉 TESTES CONCLUÍDOS")
print("=" * 60)
