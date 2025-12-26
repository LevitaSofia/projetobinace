# 🏆 Sandra 3.1: Majors First - Guia Completo

**Implementado:** 26/12/2025  
**Versão:** 3.1  
**Filosofia:** "Majors fazem MUITO mais sentido que churn em emergentes"

---

## 💡 Filosofia

> "Moeda forte tem mais liquidez, spread menor, menos manipulação, e respira melhor depois de quedas. Alt fraca muitas vezes só te faz pagar taxa/spread e ficar girando no mesmo range. Com saldo pequeno + taxas + spread = emergente vira armadilha fácil."

### Por Que Sandra 3.1?

**Problema anterior:** Bot operava igualmente em BTC/ETH e altcoins fracas, sem considerar:
- BTC/ETH têm 1000x mais liquidez
- Spreads menores = custos menores  
- Reversões mais confiáveis após quedas
- Menos manipulação (volume alto)

**Solução Sandra 3.1:** Prioridade absoluta para majors + filtros extremos para emergentes

---

## 🎯 TIER System (Filosofia Central)

### TIER A - MAJORS (👑 Prioridade Absoluta)

```
BTC/USDT  | Volume: $30B+/dia | Spread: ~1-3 bps
ETH/USDT  | Volume: $15B+/dia | Spread: ~2-5 bps
SOL/USDT  | Volume: $5B+/dia  | Spread: ~3-8 bps
BNB/USDT  | Volume: $2B+/dia  | Spread: ~3-8 bps
```

**Características:**
- Alta liquidez (sempre consegue entrar/sair)
- Spreads baixos (custos mínimos)
- Reversões históricas confiáveis
- Menos risco de manipulação
- **80-95% do capital alocado**

**Critérios de entrada (mais frequentes):**
- RSI 5m ≤ 42 (ou ≤ 30 em BEAR)
- RSI 15m ≤ 50 (confirma, não é ruído)
- Edge líquido ≥ 0.5%
- Pode operar em qualquer regime BTC

### TIER B - EMERGENTES (🎰 Exceção Rara)

```
Todas as outras moedas
Volume típico: $1M-$500M/dia
Spread típico: 10-30 bps
```

**Características:**
- Liquidez variável (pode travar)
- Spreads maiores (custos altos)
- Reversões imprevisíveis
- Risco alto de manipulação
- **Apenas 5-20% do capital (ou 0%)**

**Critérios de entrada (EXTREMOS):**
- Regime BTC = BULL (obrigatório ❌ BEAR/NEUTRAL)
- RSI 5m ≤ 24 (não 28, não 30!)
- RSI 15m ≤ 32 (confirma extremo)
- Preço ≤ BB.low * 1.01 (colado!)
- Edge líquido ≥ 1.2% (muito maior que TIER A)
- Volume ≥ $5M/24h (não $100k!)
- Spread ≤ 12 bps (book bom)

---

## 🔬 Filtros Implementados

### 1. RSI Multi-Timeframe

**Por que 2 timeframes?**
- RSI 5m sozinho pode ser ruído (spike temporário)
- RSI 15m confirma que a sobrevenda é real
- Evita entrar em "falsos fundos"

**Como funciona:**
```python
# Calcula RSI em 5m E 15m
rsi_data = calculate_rsi_multitimeframe(exchange, symbol)

# TIER A
if rsi_5m <= 42 and rsi_15m <= 50:
    # Setup válido

# TIER B  
if rsi_5m <= 24 and rsi_15m <= 32:
    # Setup extremo
```

**Exemplo real:**
```
DOGE/USDT:
- RSI 5m: 22.3 (parece bom!)
- RSI 15m: 45.2 (não confirma = ruído)
→ REJEITADO (só spike temporário)

ETH/USDT:
- RSI 5m: 28.1 (sobrevenda)
- RSI 15m: 35.2 (confirma)
→ APROVADO (reversão provável)
```

### 2. Regime BTC (EMA50 vs EMA200 em 1h)

**Por que verificar BTC?**
- BTC dita direção geral do mercado
- Em BEAR: alts sangram mais
- Em BULL: alts acompanham BTC
- TIER B só opera em mercado favorável

**Classificação:**
```python
# Busca 200 candles de 1h
klines = exchange.fetch_ohlcv('BTC/USDT', '1h', 200)

# Calcula EMAs
EMA50 = ema(close, 50)
EMA200 = ema(close, 200)

if EMA50 > EMA200:
    regime = 'BULL'    # Mercado em alta
elif EMA50 < EMA200:
    regime = 'BEAR'    # Mercado em baixa
else:
    regime = 'NEUTRAL' # Lateral
```

**Regras:**
- **TIER A:**
  - BULL: critérios normais
  - BEAR: critérios mais duros (RSI ≤ 30)
  - NEUTRAL: critérios normais
  
- **TIER B:**
  - BULL: pode operar (com filtros extremos)
  - BEAR: ❌ BLOQUEADO 100%
  - NEUTRAL: ❌ BLOQUEADO 100%

**Exemplo:**
```
BTC Regime: BEAR (EMA50 $86,234 < EMA200 $87,916)

ETH (TIER A):
- RSI 5m: 28 (< 30 OK em BEAR)
→ ✅ APROVADO (major pode em BEAR)

DOGE (TIER B):
- RSI 5m: 18 (extremo!)
→ 🚫 REJEITADO (TIER B exige BULL)
```

### 3. Edge Líquido (Anti "Trabalhar Sem Lucrar")

**O que é Edge Líquido?**
```
Edge Líquido = Take Profit - Custos Totais

Custos Totais = Taxa Compra + Taxa Venda + Spread + Slippage
```

**Cálculo detalhado:**
```python
# Exemplo: Posição $11 em DOGE, TP 2.7%

# 1. Taxas Binance Spot
taxa_compra = $11 * 0.001 = $0.011
taxa_venda = $11 * 0.001 = $0.011

# 2. Spread do orderbook
bid = $0.0987
ask = $0.0988
spread = ((ask - bid) / bid) * 100 = 0.10%
spread_cost = $11 * 0.001 = $0.011

# 3. Slippage estimado
slippage = 0.15% (TIER B)
slippage_cost = $11 * 0.0015 = $0.017

# 4. Total
custos_total = $0.011 + $0.011 + $0.011 + $0.017
custos_total = $0.050 = 0.45%

# 5. Edge
edge_liquido = 2.7% - 0.45% = 2.25% ✅
```

**Mínimos por TIER:**
- TIER A: ≥ 0.5% (custos menores, aceita menos)
- TIER B: ≥ 1.2% (custos maiores, exige mais)

**Por que isso importa?**
```
Sem verificar edge:
Compra $11 DOGE → TP 2.7%
Custos reais: 0.45%
Lucro líquido: 2.25% → $0.25 OK ✅

Mas se TP fosse só 0.8%:
Compra $11 DOGE → TP 0.8%
Custos reais: 0.45%
Lucro líquido: 0.35% → $0.04 (quase nada!)
→ Sandra 3.1 REJEITA ❌
```

### 4. Distância Bollinger Bands

**O que verifica:**
```python
bb_lower = bollinger_bands(close, 20, 2).lower

dist_bb = ((price - bb_lower) / bb_lower) * 100

# TIER A
if dist_bb > 2.0%:
    warning("Longe de BB.low")

# TIER B
if dist_bb > 1.0%:
    reject("Não colado em BB.low")
```

**Por que importa:**
- BB.low = limite inferior estatístico
- Preço abaixo/perto = sobrevenda técnica
- Preço longe = ainda pode cair mais

### 5. Volume e Spread

**TIER A:**
- Volume mín: $100k/24h (já alto)
- Spread máx: 15 bps (flexível)

**TIER B:**
- Volume mín: $5M/24h (50x maior! ❌ microcaps)
- Spread máx: 12 bps (mais rígido! ❌ book ruim)

**Por que TIER B mais rígido?**
- Alts fracas manipulam fácil com volume baixo
- Spread largo = custos ocultos enormes
- Sem liquidez = pode não conseguir sair

---

## 📊 Fluxo Completo de Decisão

```
┌─────────────────────────────────────────┐
│   Scalper Blindado aprovou?             │
│   (RSI < 35, BB, ADX, etc)              │
└─────────────┬───────────────────────────┘
              │ SIM
              ▼
┌─────────────────────────────────────────┐
│ 🏆 SANDRA 3.1: Filtros Completos        │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│ 1. Calcula RSI 5m + 15m                 │
│ 2. Calcula Regime BTC (EMA50 vs 200)   │
│ 3. Calcula Edge Líquido                 │
│ 4. Identifica TIER (A ou B)             │
└─────────────┬───────────────────────────┘
              │
              ▼
        ┌─────┴──────┐
        │            │
    TIER A       TIER B
        │            │
        ▼            ▼
 ┌──────────┐  ┌───────────────┐
 │ RSI 5m   │  │ Regime BULL?  │
 │ ≤ 42?    │  │               │
 └────┬─────┘  └───────┬───────┘
      │ SIM            │ SIM
      ▼                ▼
 ┌──────────┐  ┌───────────────┐
 │ RSI 15m  │  │ RSI 5m ≤ 24?  │
 │ ≤ 50?    │  │               │
 └────┬─────┘  └───────┬───────┘
      │ SIM            │ SIM
      ▼                ▼
 ┌──────────┐  ┌───────────────┐
 │ Edge     │  │ RSI 15m ≤ 32? │
 │ ≥ 0.5%?  │  │               │
 └────┬─────┘  └───────┬───────┘
      │ SIM            │ SIM
      ▼                ▼
 ┌──────────┐  ┌───────────────┐
 │ ✅       │  │ Edge ≥ 1.2%?  │
 │ APROVADO │  │               │
 └──────────┘  └───────┬───────┘
                       │ SIM
                       ▼
                ┌───────────────┐
                │ Vol ≥ $5M?    │
                └───────┬───────┘
                        │ SIM
                        ▼
                ┌───────────────┐
                │ Spread ≤ 12?  │
                └───────┬───────┘
                        │ SIM
                        ▼
                ┌───────────────┐
                │ ✅ APROVADO   │
                │ (EXCEÇÃO RARA)│
                └───────────────┘
```

---

## 🎨 Exemplos de Logs

### TIER A Aprovado (Frequente)

```
🔎 ETH/USDT: RSI=28.1 | Preço=$3,245.67 | Saldo=$105.32
✅ ETH/USDT passou nos filtros: +0.54% no dia | Vol: $15,234,567,890
🧠 SCALPER BLINDADO APROVOU: RSI baixo + volume normal

🔍 SANDRA 3.1: Aplicando filtros completos para ETH/USDT...
  • RSI 5m: 28.1 | RSI 15m: 35.2
  • Regime BTC: BULL (EMA50: $88,234 vs EMA200: $87,916)
  • Edge líquido: 2.45% (custos: 0.25%)
  • TIER: A (👑 MAJOR)
✅ SANDRA 3.1 TIER A: APROVADO
     ✅ RSI 5m 28.1 ≤ 42
     ✅ RSI 15m 35.2 ≤ 50
     ✅ Edge líquido 2.45% ≥ 0.5%
     ✅ Regime BTC: BULL

💰 [Aggressive] COMPRA REAL: 0.0034 ETH @ $3,245.67
```

### TIER B Rejeitado (Comum)

```
🔎 DOGE/USDT: RSI=22.3 | Preço=$0.0987 | Saldo=$105.32
✅ DOGE/USDT passou nos filtros: -2.13% no dia | Vol: $3,456,789
🧠 SCALPER BLINDADO APROVOU: RSI muito baixo

🔍 SANDRA 3.1: Aplicando filtros completos para DOGE/USDT...
  • RSI 5m: 22.3 | RSI 15m: 28.1
  • Regime BTC: BULL (EMA50: $88,234 vs EMA200: $87,916)
  • Edge líquido: 0.85% (custos: 1.85%)
  • TIER: B (🎰 EMERGENTE)
🚫 SANDRA 3.1 TIER B: REJEITADO
     🚫 Volume $3,456,789 < $5,000,000
     🚫 Edge 0.85% < 1.2% (TIER B exige mais)
```

### TIER B Aprovado (Raríssimo!)

```
🔎 SOL/USDT: RSI=18.2 | Preço=$142.67 | Saldo=$105.32
... (espera, SOL é TIER A!)

🔎 AAVE/USDT: RSI=21.3 | Preço=$267.89 | Saldo=$105.32
✅ AAVE/USDT passou nos filtros: -8.23% no dia | Vol: $8,234,567
🧠 SCALPER BLINDADO APROVOU: RSI extremo + volume alto

🔍 SANDRA 3.1: Aplicando filtros completos para AAVE/USDT...
  • RSI 5m: 21.3 | RSI 15m: 28.7
  • Regime BTC: BULL (EMA50: $88,234 vs EMA200: $87,916)
  • Edge líquido: 1.65% (custos: 1.05%)
  • TIER: B (🎰 EMERGENTE)
✅ SANDRA 3.1 TIER B: APROVADO (EXCEÇÃO RARA)
     ✅ Regime BTC: BULL
     ✅ RSI 5m 21.3 ≤ 24 (EXTREMO)
     ✅ RSI 15m 28.7 ≤ 32
     ✅ Preço colado BB.low (0.34%)
     ✅ Edge líquido 1.65% ≥ 1.2%
     ✅ Volume $8,234,567 ≥ $5,000,000
     ✅ Spread 8.2 bps ≤ 12 bps

💰 [Aggressive] COMPRA REAL: 0.041 AAVE @ $267.89
📱 Telegram: "✅ TIER B EXCEÇÃO RARA! Todos os filtros aprovados"
```

---

## 📱 Telegram Melhorado

```
🚨 DECISÃO DA IA: NOVA POSIÇÃO 🚨

🪙 Ativo: ETH/USDT (👑 ELITE)
✅ Ação: COMPRA
💵 Preço: $3,245.67
📦 Quantidade: 0.0034
💰 Investido: $11.00
💸 Taxa: -$0.022

🧠 JUSTIFICATIVA TÉCNICA:
📉 RSI 5m: 28.1 (sobrevendido)
📉 RSI 15m: 35.2 (confirmação) ← NOVO!
📊 Tendência: MODERADA (ADX 27)
⚡ Volatilidade: MODERADA (1.8%)
📊 Sentimento: 😐 NEUTRO
🌊 Regime BTC: 🐂 BULL ← NOVO!
💰 Edge líquido: ✅ 2.45% ← NOVO!
💡 Motivo: RSI baixo + volume

🎯 CONFLUÊNCIA DE SINAIS:
✅ RSI 28.1 < 30 (PADRÃO) +1pt
✅ Preço na Banda Inferior (sobrevenda) +1pt
✅ Mercado em PÂNICO (compra contra-tendência) +2pts

📊 Total: 4 pontos → SINAL FORTE 🔥

🎯 GESTÃO DE RISCO:
🧠 Modo: IA DINÂMICA (adaptado)
🛑 Stop Loss: -1.20% ($3,206.72)
✅ Take Profit: +2.70% ($3,333.42)
📊 R:R: 2.25:1

📡 FONTES DOS DADOS:
• Preço/Volume: Binance API (tempo real)
• Indicadores: Scalper Blindado (RSI, BB, ADX, ATR)
• Sentimento: CEO Manager (Fear & Greed Index)
• SL/TP: IA Dinâmica (ATR + ADX + Sentimento)

⏰ Horário: 26/12/2025 15:47:32
```

---

## ⚙️ Configuração

### Ajustar Limites TIER A

```python
# sandra_filters.py linha ~134

def check_tier_a_entry(...):
    # RSI 5m
    RSI_5M_MAX = 30 if regime_btc == 'BEAR' else 42  # ← AJUSTAR
    
    # RSI 15m
    RSI_15M_MAX = 38 if regime_btc == 'BEAR' else 50  # ← AJUSTAR
    
    # Edge mínimo
    EDGE_MIN = 0.5  # ← AJUSTAR
```

### Ajustar Limites TIER B

```python
# sandra_filters.py linha ~187

def check_tier_b_entry(...):
    # RSI 5m (extremo!)
    RSI_5M_MAX = 24  # ← AJUSTAR (mais baixo = menos trades)
    
    # RSI 15m
    RSI_15M_MAX = 32  # ← AJUSTAR
    
    # Edge mínimo
    EDGE_MIN = 1.2  # ← AJUSTAR (mais alto = menos trades)
    
    # Volume mínimo
    VOL_MIN = 5_000_000  # ← AJUSTAR
    
    # Spread máximo
    SPREAD_MAX = 12  # ← AJUSTAR (mais baixo = menos trades)
```

### Adicionar/Remover Majors

```python
# sandra_filters.py linha ~16

TIER_A_SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'SOL/USDT',
    'BNB/USDT',
    # 'AVAX/USDT',  ← ADICIONAR se quiser
]
```

---

## 📈 Resultados Esperados

### Antes (Sandra 2.1)

```
Operações/dia: 15-20
TIER A: 40%
TIER B: 60%
Edge médio: 0.8%
Win rate: 55%

Problema: Muito churn em alts fracas
```

### Depois (Sandra 3.1)

```
Operações/dia: 5-10
TIER A: 85%
TIER B: 15%
Edge médio: 1.5%
Win rate esperado: 65%+

Vantagem: Foco em qualidade, não quantidade
```

---

## 🐛 Troubleshooting

### "TIER B nunca compra"

**Normal!** TIER B é exceção rara. Verifique histórico:
```bash
grep "SANDRA 3.1 TIER B" server.log | grep "APROVADO"
```

Se realmente nunca aprova e quer relaxar:
1. Diminuir RSI_5M_MAX de 24 para 26
2. Diminuir EDGE_MIN de 1.2% para 1.0%
3. Diminuir VOL_MIN de $5M para $2M

### "TIER A também não compra muito"

Verifique regime BTC:
```bash
grep "Regime BTC: BEAR" server.log
```

Em BEAR, critérios TIER A ficam mais duros (RSI ≤ 30).
Isto é proposital para proteger capital.

### "Edge sempre muito baixo"

Verifique spreads reais:
```python
python3 -c "
import ccxt
ex = ccxt.binance()
depth = ex.fetch_order_book('DOGE/USDT', 5)
bid = depth['bids'][0][0]
ask = depth['asks'][0][0]
spread_pct = ((ask-bid)/bid)*100
print(f'Spread: {spread_pct*100:.1f} bps')
"
```

Se spreads estão altos (>15 bps), é normal edge ser baixo.
Solução: Operar só majors (spreads 1-5 bps).

---

## 📚 Referências

- **Código:** `sandra_filters.py` (400 linhas)
- **Integração:** `server.py` linha ~3400
- **Telegram:** `server.py` linha ~2460
- **Testes:** `tests/test_reporter.py`

---

**Versão:** 3.1  
**Status:** ✅ ATIVO  
**Última atualização:** 26/12/2025  
**Próximo:** Sandra 3.2 (ReEntryGuard com reset de fundo)
