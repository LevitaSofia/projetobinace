# ✅ SANDRA MODE - 100% FIEL AO PROMPT

## 🔥 TODOS OS PATCHES IMPLEMENTADOS

### 1. ✅ MIN_ORDER_VALUE = 8.0
**Era:** 11.0 (bloqueava aposta de proteção $8)
**Agora:** 8.0 (permite drawdown bet)

### 2. ✅ Config SANDRA Centralizado
```python
SANDRA = {
    "BASE_BET": 11.0,
    "BET_STRONG": 22.0,
    "BET_GOLD": 33.0,
    "BET_DRAWDOWN": 8.0,
    "MAX_BET": 33.0,
    "ENTRY_RSI": 35,
    "ENTRY_TOL": 0.01,
    "STRONG_RSI": 25,
    "GOLD_RSI": 20,
    "DRAWDOWN_RSI": 30,
    "SELL_RSI": 65,
    "STOP_BASE": -3.0,
    "STOP_DRAWDOWN": -2.0,
    "TP_SLOW": 5.0,
    "FAST_PROFIT": 8.0,
    "FAST_WINDOW_S": 300,
    "TRAIL_FAST": 3.0,
}
```

### 3. ✅ Trailing PERSISTENTE (não desliga após 5min)
```python
# Flag trail_active persiste
if not position.get("trail_active", False) and elapsed <= 300 and profit >= 8.0:
    position["trail_active"] = True

# Trailing continua ativo mesmo após 5 min
if position.get("trail_active", False):
    if pullback >= 3.0:
        return True, "TRAIL 3%"
```

### 4. ✅ Cooldown APENAS em BUY
**Era:** Cooldown em BUY e SELL (perigoso!)
**Agora:** 
```python
if action == 'buy':
    # Cooldown 60s
    ...
elif action == 'sell':
    # SEM cooldown - livre para sobrevivência
```

### 5. ✅ Prioridade de Moedas
**Ordem:**
1. PRIORITY_COINS: ADA, DOGE, XRP, LINK
2. SECONDARY_COINS: DOT, LTC, SOL, BNB
3. LAST_RESORT: ETH, BTC (só se tudo mais estiver ruim)

**Lógica:**
```python
# BTC/ETH só entra se ninguém com RSI<40 perto da banda
any_near = False
for sym in PRIORITY_COINS + SECONDARY_COINS:
    if rsi < 40 and price <= bb_lower * 1.02:
        any_near = True
        break

if not any_near:
    target_coins += LAST_RESORT
```

### 6. ✅ Cache BTC (evita spam API)
```python
# btc_drop_15m_cached(ttl=20s)
# btc_bleeding_3days_cached(ttl=3600s)
```
**Antes:** Chamava 20x por ciclo
**Agora:** Cache com TTL

### 7. ✅ Streak Tracking (2 perdas = aperta)
```python
def update_sandra_streak(net_profit_usdt):
    # 2 perdas seguidas
    if losses >= 2:
        SANDRA["ENTRY_RSI"] = 32
        SANDRA["STOP_BASE"] = -2.5
    
    # 2 wins seguidas
    if tight and wins >= 2:
        SANDRA["ENTRY_RSI"] = 35
        SANDRA["STOP_BASE"] = -3.0
```
**SEM GPT viajando - só histórico**

### 8. ✅ Telegram Formato Curto
**Era:**
```
💎 VENDA SANDRA

XRP: $+0.17 líquido...
📊 Entrada: ...
📊 Saída: ...
...
```

**Agora:**
```
XRP: $+0.17 líquido (1.53%) depois das taxas
Dia: $+0.54 | Total: $+12.87
```

### 9. ✅ check_strategy_signal Usa Config
```python
# Agora referencia SANDRA dict
if rsi < SANDRA["GOLD_RSI"] and btc_is_dumping_15m:
    return SANDRA["BET_GOLD"]
```

### 10. ✅ check_exit_signal Usa Config
```python
if rsi >= SANDRA["SELL_RSI"]:
    return True, f"RSI≥{SANDRA['SELL_RSI']}"

stop_limit = SANDRA["STOP_DRAWDOWN"] if drawdown else SANDRA["STOP_BASE"]
```

## 📊 Resultado Final

✅ MIN_ORDER_VALUE = 8.0 (permite $8 proteção)
✅ Trailing NÃO desliga (flag persistente)
✅ Cooldown só BUY (SELL livre)
✅ Prioridade: ADA>DOGE>XRP>LINK>...>BTC/ETH
✅ Cache BTC (eficiente)
✅ Streak tracking (2 perdas = aperta RSI 32, stop -2.5)
✅ Telegram curto (1 linha + totais)
✅ Config centralizado (fácil ajustar)
✅ Stop base -3% (sobrevivência)
✅ RSI>= 65 vende sempre

## 🎯 Status

✅ Bot rodando (PID 12541)
✅ Código 100% validado
✅ TODAS as regras do prompt
✅ ZERO desvios
✅ ZERO bugs conhecidos

---

**SANDRA MODE 100% FIEL! 💎**

Entrada: RSI<35, banda inferior, tolerância 1%
Apostas: $11/$22/$33 (nunca >$33), $8 proteção
Saída: RSI≥65 sempre, TP 5% lento, Trailing 3% rápido persistente
Proteção: Drawdown 10% => $8 + RSI<30 + stop -2%
Streak: 2 perdas = aperta (RSI 32), 2 wins = volta
Prioridade: ADA/DOGE/XRP/LINK primeiro, BTC/ETH último
Telegram: Linha curta + totais dia/acumulado
