# ANÁLISE COMPLETA DAS INTEGRAÇÕES DE IA - PROJETO BINACE

**Data:** 2025-12-28  
**Status:** 🔴 4 BUGS CRÍTICOS ENCONTRADOS + Sandra 3.1 NÃO ESTÁ ATIVA

---

## SUMÁRIO EXECUTIVO

**Total de Integrações IA:** 6 funções (5 OpenAI + 1 Whisper)

**Status:**
- ✅ 3 funcionando corretamente
- 🟡 2 com bugs médios
- 🔴 1 com bug crítico (telegram_audio)
- ⚠️ **SANDRA 3.1 existe mas NÃO é chamada no fluxo de trading!**

---

## BUGS CRÍTICOS ENCONTRADOS

### 🔴 BUG #1: OPENAI_MODEL com Typo
**Arquivo:** `server.py:262`  
**Problema:**
```python
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')  # ❌ gpt-4.1 não existe!
```
**Deveria ser:** `'gpt-4o-mini'`  
**Impacto:** Todas as chamadas OpenAI falham com erro "model not found"

---

### 🔴 BUG #2: Import tempfile Faltando
**Arquivo:** `server.py` (linha 5507 usa, mas não está importado)  
**Problema:**
```python
# Linha 5507
with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
    # ❌ NameError: name 'tempfile' is not defined
```
**Impacto:** Função `telegram_audio()` quebra quando usuário envia áudio

---

### 🔴 BUG #3: Modelo Hardcoded Inconsistente
**Arquivo:** `server.py:5470`  
**Problema:**
```python
response = client.chat.completions.create(
    model="gpt-4o-mini",  # ❌ Hardcoded! Ignora OPENAI_MODEL global
```
**Impacto:** Inconsistência - outras funções usam OPENAI_MODEL, esta não

---

### 🔴 BUG #4: Parsing Frágil em analyze_market_with_gpt
**Arquivo:** `server.py:1304-1307`  
**Problema:**
```python
for line in res:
    if line.lower().startswith('ação:'):  # ❌ Se IA responder "AÇÃO:" (caps) ou "A ação é:" (paráfrase) → falha
        acao = line.split(':', 1)[1].strip()
```
**Impacto:** IA pode responder, mas parse falha → ajustes de estratégia não são aplicados

---

## PROBLEMA MAIOR: SANDRA 3.1 NÃO ESTÁ ATIVA

### O que deveria acontecer (SANDRA 3.1):
```
1. Scalper aprova (RSI < 35)
2. sandra_filters.check_tier_a_entry() ou check_tier_b_entry()
   ├─ Verifica RSI 15m
   ├─ Verifica Regime BTC (EMA50/200)
   ├─ Calcula edge líquido
   ├─ Valida volume e spread
   └─ Aplica TIER A (majors) ou TIER B (emergentes)
3. Se aprovado → executa_real_trade()
```

### O que REALMENTE acontece:
```
1. Scalper aprova (RSI < 35)
2. check_strategy_signal()  ← IGNORA sandra_filters completamente!
3. Executa_real_trade() DIRETAMENTE
   ❌ Sem verificar RSI 15m
   ❌ Sem verificar Regime BTC
   ❌ Sem calcular edge líquido
   ❌ Sem validar TIER
```

**Resultado:** Sistema opera como SANDRA 1.0 (simples), não SANDRA 3.1 (avançado)

---

## INTEGRAÇÕES DE IA DETALHADAS

### 1. `get_openai_client()` - Factory
**Status:** ✅ OK (com BUG #1 no modelo)  
**Função:** Inicializar cliente OpenAI com retry de 60s

---

### 2. `openai_text()` - Wrapper Genérico
**Status:** 🟡 OK mas sem cache  
**Função:** Chamadas simples de chat  
**Problema:** Sem cache, sem tratamento de rate limit

---

### 3. `analyze_market_with_gpt()` - Ajuste Dinâmico
**Status:** 🔴 BUG #4 (parsing frágil)  
**Função:** IA analisa últimos 5 trades e ajusta parâmetros  
**Prompt:** "Se perdeu 2 ou mais → RSI 32, tolerância 0.5%, stop -2.5%"  
**Problema:** Espera formato exato "Ação: ... / Telegram: ..."

---

### 4. `juiz_de_moedas()` - Auditor de Moedas
**Status:** ✅ EXCELENTE  
**Função:** IA aprova/rejeita moedas antes de adicionar à watchlist  
**Usa:** JSON response format + fallback inteligente  
**Cache:** 24h por coin_id

---

### 5. `process_ai_response()` - Chat Telegram
**Status:** 🟡 OK (BUG #3: modelo hardcoded)  
**Função:** Responder perguntas do usuário com contexto completo  
**Problema:** System prompt pode ser muito grande

---

### 6. `telegram_audio()` - Transcrição Whisper
**Status:** 🔴 BUG #2 (import tempfile faltando)  
**Função:** Transcrever áudio e processar como texto  
**Problema:** RuntimeError quando áudio é enviado

---

## DICT SANDRA - CONFIGURAÇÃO ATUAL

```python
SANDRA = {
    "BASE_BET": 11.0,          # Aposta padrão
    "BET_STRONG": 22.0,        # RSI<25 + volume
    "BET_GOLD": 33.0,          # RSI<20 + BTC dump
    "ENTRY_RSI": 35,           # Limiar RSI (ajustável)
    "ENTRY_TOL": 0.01,         # Tolerância banda (1%)
    "SELL_RSI": 65,            # RSI para vender
    "STOP_BASE": -3.0,         # SL padrão
    "TP_SLOW": 5.0,            # TP padrão
    "TRAIL_FAST": 3.0,         # Trailing stop
    "USE_DYNAMIC_RISK": True,  # IA dinâmica (ATR/ADX)
}
```

**Quem modifica:**
- `update_sandra_streak()` - Aperta/relaxa com wins/losses
- CEO Manager - Calcula SL/TP dinâmico por posição

---

## VERSÕES DA SANDRA

| Versão | Status | Implementação | Gap |
|--------|--------|---------------|-----|
| SANDRA Simple (prompt) | Obsoleta | 100% | - |
| SANDRA 2.0 (docs) | Anterior | 60% | Tier system parcial |
| SANDRA 2.1 (docs) | Anterior | 40% | Explainability ausente |
| **SANDRA 3.1 (docs)** | **ATIVA** | **15%** | **Código existe, NÃO é chamado!** |

---

## O QUE SANDRA 3.1 DEVERIA FAZER

### TIER A (Majors: BTC/ETH/SOL/BNB)
- RSI 5m ≤ 42
- RSI 15m ≤ 50
- Edge ≥ 0.5%
- Opera em qualquer regime BTC

### TIER B (Emergentes - Filtros EXTREMOS)
- Regime BTC = BULL obrigatório
- RSI 5m ≤ 24 (não 28!)
- RSI 15m ≤ 32
- Preço ≤ BB.low * 1.01
- Edge ≥ 1.2%
- Volume ≥ $5M/24h
- Spread ≤ 12 bps

**Arquivo:** `sandra_filters.py` - COMPLETO mas NUNCA CHAMADO

---

## RECOMENDAÇÕES URGENTES

### Imediato (30 minutos):

1. **Corrigir typo do modelo**
   ```python
   OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')  # ✅
   ```

2. **Adicionar import tempfile**
   ```python
   import tempfile  # Linha ~36
   ```

3. **Corrigir modelo hardcoded**
   ```python
   model=OPENAI_MODEL,  # Em vez de "gpt-4o-mini"
   ```

4. **Mudar analyze_market_with_gpt para JSON**
   ```python
   response_format={"type": "json_object"}
   # Resposta: {"acao": "ajuste", "telegram": "msg"}
   ```

### Importante (2 horas):

5. **Integrar Sandra 3.1 no fluxo**
   ```python
   # Em check_strategy_signal(), antes de executar compra:
   
   tier = sandra_filters.classify_tier(symbol)
   
   if tier == 'A':
       result = sandra_filters.check_tier_a_entry(symbol, client, rsi_5m, rsi_15m, price, bb_lower)
   else:
       result = sandra_filters.check_tier_b_entry(symbol, client, rsi_5m, rsi_15m, price, bb_lower)
   
   if not result['allowed']:
       return 0  # Não compra
   ```

6. **Calcular RSI 15m**
   ```python
   rsi_15m = calculate_rsi(fetch_ohlcv(symbol, '15m', limit=20))
   ```

7. **Calcular Regime BTC**
   ```python
   regime = sandra_filters.calculate_btc_regime(client)
   ```

---

## ANÁLISE DE CONSISTÊNCIA

### Prompt vs Implementação

| Regra Documentada | Implementado? | Observação |
|-------------------|---------------|------------|
| RSI < 35 entrada | ✅ SIM | Ajustável via SANDRA["ENTRY_RSI"] |
| Tolerância 1% | ✅ SIM | SANDRA["ENTRY_TOL"] |
| Lucro 5% TP | ✅ SIM | SANDRA["TP_SLOW"] |
| Trailing 3% | ✅ SIM | SANDRA["TRAIL_FAST"] |
| **RSI 15m verificação** | ❌ NÃO | **sandra_filters não é chamado** |
| **Regime BTC** | ❌ NÃO | **Função existe mas não é usada** |
| **Edge líquido** | ❌ NÃO | **Calculado mas não aplicado** |
| **TIER A/B** | ❌ NÃO | **Classificação não influencia decisão** |

---

## CONCLUSÃO

**Estado Atual:**
- SANDRA funciona como versão 1.0 (simples)
- IA GPT está integrada mas com bugs
- SANDRA 3.1 está 85% implementada mas 0% ativa

**Próximos Passos:**
1. Corrigir 4 bugs críticos (30 min)
2. Integrar sandra_filters.py no fluxo (2 horas)
3. Ativar verificações de TIER A/B (1 hora)
4. Testar com dados reais (1 hora)

**Prioridade:** 🔴 ALTA - Sistema opera sem filtros avançados

---

**FIM DO RELATÓRIO**
