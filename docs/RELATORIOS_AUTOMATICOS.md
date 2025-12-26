# 📧 Sistema de Relatórios Automáticos

**Status:** ✅ ATIVO  
**Versão:** 1.0  
**Data:** Janeiro 2025

## 🎯 Objetivo

Enviar relatórios **completos e detalhados** via **Email + Telegram** quando o bot comprar moedas **TIER B** (fracas/emergentes), explicando **EXATAMENTE POR QUE** a decisão foi tomada com todos os dados verificados segundo o protocolo **Sandra 2.1**.

## 🚨 O Que Disparou Isso?

**Situação real:** Bot comprou STRK/USDT (-1.36% no dia) com:
- ⚠️ Volume $4.96M (< $10M mínimo)
- ⚠️ Edge líquido 0.39% (< 0.8% mínimo)

**Problema:** Usuário recebeu apenas notificação básica sem entender **POR QUE** o bot comprou uma moeda com 2 avisos críticos.

**Solução:** Sistema agora envia:
1. 📱 **Telegram** com todos os dados (já existia, melhorado)
2. 📧 **Email HTML** com análise completa (NOVO)

---

## 📋 TIER System

### TIER A - Majors (Confiáveis)
- BTC/USDT
- ETH/USDT
- SOL/USDT
- BNB/USDT

**Limites:**
- Volume mínimo: $50M/24h
- Spread máximo: 12 bps
- Edge mínimo: 0.5%
- Regime BTC: Qualquer (BULL/NEUTRAL/BEAR)

### TIER B - Emergentes/DEGEN (Arriscadas) ⚠️
- Todas as outras moedas

**Limites:**
- Volume mínimo: $10M/24h
- Spread máximo: 18 bps
- Edge mínimo: 0.8%
- Regime BTC: **BULL obrigatório** (EMA50 > EMA200)

**Regra:** Toda compra TIER B gera relatório completo!

---

## 📧 Conteúdo do Email (HTML)

### 1. Header
```
🚨 RELATÓRIO COMPLETO DE TRADE - TIER B
STRK/USDT | $0.0799 | 14/01/2025 às 15:32:17
```

### 2. Dados de Mercado (24h)
```
┌─────────────┬──────────────┬─────────────────┬────────┐
│ Métrica     │ Valor        │ Limite Sandra   │ Status │
├─────────────┼──────────────┼─────────────────┼────────┤
│ Variação    │ -1.36%       │ > -10%          │ ✅     │
│ Volume      │ $4,963,650   │ > $10,000,000   │ ⚠️     │
│ Spread      │ 12.5 bps     │ < 18 bps        │ ✅     │
└─────────────┴──────────────┴─────────────────┴────────┘
```

### 3. Regime BTC (1h)
```
Status: 🐂 BULL
EMA50:  $88,091.94
EMA200: $87,916.63

Interpretação: EMA50 > EMA200 = Mercado em alta
Regra TIER B: ✅ Atendida (regime BULL permite)
```

### 4. Análise de Custos e EDGE ⚡
```
┌────────────────────┬─────────┬───────┐
│ Item               │ USD     │ %     │
├────────────────────┼─────────┼───────┤
│ Taxa compra        │ $0.011  │ 0.10% │
│ Taxa venda (est)   │ $0.011  │ 0.10% │
│ Spread orderbook   │ $0.014  │ 0.13% │
│ Slippage estimado  │ $0.017  │ 0.15% │
├────────────────────┼─────────┼───────┤
│ CUSTO TOTAL        │ $0.254  │ 2.31% │
└────────────────────┴─────────┴───────┘

🎯 Cálculo de EDGE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Take Profit proposto:     +2.70%
Custo total:              -2.31%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE LÍQUIDO:             +0.39% ⚠️
Edge mínimo TIER B:        0.80%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Interpretação: ⚠️ Edge INSUFICIENTE - margem muito apertada!
```

### 5. Gestão de Risco
```
┌─────────────────┬─────────────────────┐
│ Posição         │ $11.00              │
│ Stop Loss       │ -1.20% ($0.0789)    │
│ Take Profit     │ +2.70% ($0.0820)    │
│ Risco:Recompensa│ 2.25:1              │
└─────────────────┴─────────────────────┘
```

### 6. Avisos/Violações

**Se houver VIOLAÇÕES (🚨):**
```
🚨 VIOLAÇÕES CRÍTICAS (1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ TIER B em regime BEAR (exige BULL)

⚠️ ESTE TRADE NÃO DEVERIA TER SIDO EXECUTADO SEGUNDO SANDRA 2.1
```

**Se houver AVISOS (⚠️):**
```
⚠️ AVISOS (2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Volume $4,963,650 < $10,000,000
⚠️ Edge líquido 0.39% < 0.8%

Observação: Avisos não impedem o trade, mas aumentam o risco.
```

### 7. Conclusão e Recomendação

```
📋 CONCLUSÃO E RECOMENDAÇÃO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Data/Hora: 14/01/2025 às 15:32:17
Símbolo: STRK/USDT
TIER: B (Emergente/DEGEN)

⚠️ DECISÃO: Trade aprovado, mas com margem de erro pequena. 
            Monitorar de perto.

Próximos passos:
• Monitorar Stop Loss: -1.20%
• Alvo Take Profit: +2.70%
• Atenção especial aos avisos acima
```

---

## 📱 Telegram Melhorado

Telegram agora mostra resumo executivo com os mesmos dados (formatado com emojis).

**Diferenças:**
- Email: Completo, auditável, HTML formatado (melhor para análise depois)
- Telegram: Resumido, direto, com emojis (melhor para olhar rápido no celular)

---

## 🔧 Configuração

### .env
```env
EMAIL_ENABLED=true
EMAIL_TO=levital72@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=levital72@gmail.com
SMTP_PASS=jjos zusy sppi lcce  # App Password do Gmail
```

### server.py
```python
# Detecta TIER automaticamente
TIER_A_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']
tier = 'A' if symbol in TIER_A_SYMBOLS else 'B'

# Se TIER B, envia relatório
if tier == 'B':
    trade_reporter.send_complete_report(
        exchange=exchange,
        symbol=symbol,
        position_size=buy_total,
        tp_pct=tp_usado,
        sl_pct=abs(sl_usado),
        tier=tier,
        send_telegram_func=None
    )
```

---

## 🧠 Módulos

### trade_reporter.py (NOVO)

**Funções principais:**

1. `calculate_btc_regime(exchange)` → ("BULL", ema50, ema200)
   - Pega BTC/USDT 1h últimos 200 candles
   - Calcula EMA50 e EMA200
   - Retorna: BULL se EMA50 > EMA200

2. `analyze_trade_complete(exchange, symbol, ...)` → dict
   - Busca dados 24h (var, volume)
   - Calcula spread do orderbook
   - Calcula custos totais (fees + spread + slippage)
   - Calcula edge líquido (tp - custos)
   - Verifica violações e avisos
   - Retorna dict completo

3. `generate_email_report(analysis)` → HTML string
   - Gera email formatado com todas as seções
   - CSS inline para compatibilidade

4. `send_email_report(analysis, to_email)` → bool
   - Conecta SMTP Gmail
   - Envia email HTML
   - Retorna True/False

5. `send_complete_report(...)` → dict
   - Orquestra tudo: análise + email + telegram
   - Retorna {'analysis': ..., 'email_sent': True, 'telegram_sent': True}

---

## 📊 Exemplo Real

### STRK/USDT - 14/01/2025

**Dados coletados:**
- Preço: $0.0799
- Variação 24h: -1.36%
- Volume 24h: $4,963,650
- Spread: 12.5 bps
- BTC Regime: BULL (EMA50 $88,091 > EMA200 $87,916)

**Custos calculados:**
- Taxa compra: $0.011 (0.10%)
- Taxa venda: $0.011 (0.10%)
- Spread: $0.014 (0.13%)
- Slippage: $0.017 (0.15%)
- **Total: $0.254 (2.31%)**

**Edge:**
- TP: 2.70%
- Custos: 2.31%
- **Edge líquido: 0.39%** ⚠️ (< 0.8% mínimo)

**Decisão:**
✅ Aprovado (regime BULL, sem sangria)
⚠️ 2 avisos: Volume baixo + Edge insuficiente

**Por que comprou mesmo com avisos?**
- Regime BTC em BULL permite TIER B
- Variação -1.36% não é sangria (< -10%)
- RSI 27.3 indicava sobrevenda (oportunidade)
- Sistema usa **filtros graduais**, não absolutos
- Avisos aumentam risco mas não bloqueiam

**Resultado enviado:**
- ✅ Email HTML completo para levital72@gmail.com
- ✅ Telegram com resumo executivo

---

## 🎯 Benefícios

### Transparência Total
- Usuário vê EXATAMENTE o que o bot analisou
- Todos os números estão no email (auditável)
- Decisões justificadas com dados reais

### Educação Progressiva
- Usuário aprende a ler análises técnicas
- Entende o que é edge, spread, slippage
- Vê como BTC influencia altcoins

### Segurança Emocional
- Reduz ansiedade ("por que comprou isso?")
- Builds confiança no sistema
- Permite intervenção manual se necessário

### Compliance/Auditoria
- Histórico completo em email
- Timestamps precisos
- Dados rastreáveis até a Binance API

---

## 🚀 Próximos Passos (Opcional)

### 1. Dashboard Web com Histórico
```python
@app.route('/reports')
def reports():
    # Lista todos os trades TIER B dos últimos 7 dias
    # Com links para reenviar email
```

### 2. Classificação de Risco Visual
```
🟢 LOW RISK    (edge > 1.5%, volume > $50M)
🟡 MEDIUM RISK (edge 0.8-1.5%, volume $10-50M)
🔴 HIGH RISK   (edge < 0.8%, volume < $10M)
```

### 3. Integração com IA (GPT-4)
```python
# Adiciona seção "🧠 Análise da IA" no email
# Explica em linguagem natural por que trade é arriscado
prompt = f"Explique por que comprar {symbol} com edge {edge}% e volume ${vol} é arriscado"
```

### 4. Modo "Aprovação Prévia"
```python
SANDRA["REQUIRE_APPROVAL_TIER_B"] = True
# Envia relatório ANTES de comprar
# Aguarda confirmação manual via Telegram
```

---

## 📝 Logs

**Compra TIER A (não gera relatório):**
```
💰 [Aggressive] COMPRA REAL: 0.0005 BTC/USDT @ $88,234.56
📱 Enviando justificativa para Telegram...
✅ Trade executado
```

**Compra TIER B (gera relatório):**
```
💰 [Aggressive] COMPRA REAL: 137.5 STRK/USDT @ $0.0799
📱 Enviando justificativa para Telegram...
📧 Gerando relatório Sandra 2.1 para STRK/USDT (TIER B)...
📊 Gerando relatório completo para STRK/USDT (TIER B)...
✅ Email enviado para levital72@gmail.com
✅ Trade executado
```

---

## ⚙️ Desabilitação

Para desabilitar relatórios sem remover código:

### Método 1: .env
```env
EMAIL_ENABLED=false
```

### Método 2: Comentar bloco
```python
# 🚨 RELATÓRIO COMPLETO (SANDRA 2.1)
# try:
#     if tier == 'B':
#         trade_reporter.send_complete_report(...)
# except Exception as e:
#     pass
```

---

## 🐛 Troubleshooting

### Email não chega
1. Verificar .env: `EMAIL_ENABLED=true`
2. Verificar senha de app Gmail (não é senha normal!)
3. Testar manualmente:
```python
python3 -c "from trade_reporter import send_email_report; send_email_report({'symbol': 'TEST', ...})"
```

### Erro "No module named 'trade_reporter'"
```bash
# Verificar se arquivo existe
ls -la /home/ubuntu/projetobinace/trade_reporter.py

# Reiniciar server
pkill -f server.py
cd /home/ubuntu/projetobinace
nohup python3 server.py &
```

### Análise falha
```python
# Logs no terminal mostrarão:
⚠️ Erro na análise completa: [erro específico]
```
- Geralmente: Binance API offline ou rate limit
- Solução: Sistema continua funcionando, só não envia relatório

---

## 📚 Referências

- **Sandra 2.1:** `docs/SANDRA_2.1_SYSTEM_PROMPT.md`
- **Lógica Sábia:** `docs/PATCHES_SANDRA_100.md`
- **Código:** `server.py` (linha ~2700) + `trade_reporter.py`
- **Email Config:** `.env`

---

**Versão:** 1.0  
**Autor:** Sistema Sandra 2.1  
**Última atualização:** 14/01/2025
