# 🤖 Bot de Trading Binance - Documentação Completa

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Estratégia de Trading](#estratégia-de-trading)
3. [Regras de Compra](#regras-de-compra)
4. [Regras de Venda](#regras-de-venda)
5. [Proteções Anti-Precipitação](#proteções-anti-precipitação)
6. [Configurações](#configurações)
7. [Comandos Telegram](#comandos-telegram)
8. [Arquitetura do Sistema](#arquitetura-do-sistema)
9. [Histórico de Correções](#histórico-de-correções)

---

## 🎯 Visão Geral

Bot de trading automatizado para Binance que monitora múltiplas criptomoedas e executa operações de compra/venda baseado em indicadores técnicos (RSI e Bandas de Bollinger).

### Características Principais:
- ✅ Trading real na Binance (SPOT)
- ✅ Monitoramento de 10 criptomoedas simultaneamente
- ✅ Notificações via Telegram
- ✅ Dashboard web em tempo real
- ✅ Relatórios automáticos (8h, 12h, 18h, 22h)
- ✅ Chat com IA (GPT) para análises
- ✅ Conversão automática BRL → USDT

---

## 📈 Estratégia de Trading

### Indicadores Utilizados:

| Indicador | Configuração | Uso |
|-----------|--------------|-----|
| **RSI** | Período 14, Timeframe 1h | Identificar sobrecompra/sobrevenda |
| **Bollinger Bands** | Período 20, Desvio 2.0 | Identificar extremos de preço |

### Interpretação:

```
RSI < 30  → Mercado SOBREVENDIDO (bom para comprar)
RSI > 70  → Mercado SOBRECOMPRADO (bom para vender)

Preço < BB Lower → Preço muito baixo (bom para comprar)
Preço > BB Upper → Preço muito alto (bom para vender)
```

---

## 🛒 Regras de Compra

### Condições OBRIGATÓRIAS (todas devem ser verdadeiras):

```python
# Função: check_strategy_signal()

1. RSI < 35                    # Mercado sobrevendido
2. Preço <= BB_Lower + 1%      # Preço na banda inferior (com tolerância)
3. Saldo USDT >= $11           # Saldo mínimo para operar
4. Sem posição aberta          # Só uma posição por vez
```

### Moedas Monitoradas (WATCHLIST):

```python
WATCHLIST = [
    'XRP/USDT',    # ~$2
    'ADA/USDT',    # ~$1
    'DOGE/USDT',   # ~$0.40
    'DOT/USDT',    # ~$8
    'LINK/USDT',   # ~$15
    'LTC/USDT',    # ~$100
    'BNB/USDT',    # ~$700
    'ETH/USDT',    # ~$4000
    'SOL/USDT',    # ~$200
    'BTC/USDT',    # ~$100000
]
```

### Valor por Operação:
- **Investimento**: $10-11 USDT por trade
- **Mínimo**: $11 USDT (MIN_ORDER_VALUE)

---

## 💰 Regras de Venda

### Função: `check_exit_signal()`

A venda é baseada em **LUCRO + RSI** para confirmar o momento certo:

| Condição | RSI Mínimo | Ação |
|----------|------------|------|
| Lucro ≥ 5.0% | Qualquer | ✅ **VENDE SEMPRE** |
| Lucro ≥ 3.5% | RSI > 55 | ✅ Vende |
| Lucro ≥ 2.5% | RSI > 60 | ✅ Vende |
| Lucro ≥ 2.0% | RSI > 65 | ✅ Vende |
| Lucro ≥ 1.5% | RSI > 70 | ✅ Vende |
| Banda Superior + Lucro ≥ 1.5% | RSI > 55 | ✅ Vende |

### Stop Loss:

| Condição | Ação |
|----------|------|
| Prejuízo ≤ -3.0% | 🛑 Stop Loss |
| Prejuízo ≤ -5.0% | 🚨 Emergência (vende mesmo com RSI baixo) |

---

## 🛡️ Proteções Anti-Precipitação

### Proteção 1: RSI Baixo (em `check_exit_signal`)

```python
# Se RSI < 40 e prejuízo > -5%, NÃO VENDE
# Mercado sobrevendido = pode subir, aguarda recuperação

if rsi < 40 and profit_pct > -5:
    print("⏳ RSI baixo - Aguardando recuperação...")
    return False  # NÃO VENDE
```

### Proteção 2: Bloqueio na Execução (em `execute_real_trade`)

```python
# Dupla verificação antes de executar a venda

# BLOQUEIO 1: RSI muito baixo
if current_rsi < 40 and profit_check > -5:
    print("🛡️ VENDA BLOQUEADA! RSI muito baixo")
    return False

# BLOQUEIO 2: Prejuízo não atingiu stop loss
if profit_check < 0 and profit_check > -3:
    print("🛡️ VENDA BLOQUEADA! Prejuízo não atingiu stop loss")
    return False
```

### Resumo das Proteções:

| Situação | Antes | Agora |
|----------|-------|-------|
| RSI < 40 | Vendia no stop | ❌ **NÃO VENDE** |
| Prejuízo 0% a -3% | Vendia | ❌ **Aguarda** |
| Prejuízo -3% a -5% | - | ✅ Stop Loss |
| Prejuízo < -5% | - | ✅ Emergência |

---

## ⚙️ Configurações

### Arquivo `.env`:

```env
BINANCE_API_KEY=sua_api_key
BINANCE_SECRET=sua_secret_key
TELEGRAM_TOKEN=seu_token_telegram
TELEGRAM_CHAT_ID=seu_chat_id
OPENAI_API_KEY=sua_openai_key (opcional)
```

### Constantes Importantes:

```python
AMOUNT_INVEST = 11.0        # Valor por trade em USDT
MIN_ORDER_VALUE = 11        # Mínimo para abrir posição
TRADE_COOLDOWN = 60         # Segundos entre trades
FEE_RATE = 0.001            # Taxa Binance (0.1%)

# Relatórios automáticos
REPORT_HOURS = [8, 12, 18, 22]
```

---

## 📱 Comandos Telegram

### Comandos Disponíveis:

| Comando | Alias | Descrição |
|---------|-------|-----------|
| `/start` | - | Mensagem de boas-vindas |
| `/ajuda` | `/help` | Lista de comandos |
| `/status` | - | Status geral do bot |
| `/saldo` | - | Ver saldos da conta |
| `/posicao` | `/position` | Ver posição aberta |
| `/moedas` | `/coins` | Ver todas as moedas monitoradas |
| `/relatorio` | `/report` | Gerar relatório de mercado |
| `/comprar <MOEDA>` | `/buy` | Forçar compra (ex: `/comprar XRP`) |
| `/converter` | `/convert` | Converter BRL → USDT |
| `/ligar` | `/on` | Ligar o bot |
| `/desligar` | `/off` | Desligar o bot |

### Chat com IA:
Qualquer mensagem de texto (não comando) é respondida pelo GPT com contexto do mercado.

---

## 🏗️ Arquitetura do Sistema

### Estrutura de Arquivos:

```
projetobinace/
├── server.py           # Servidor principal (Flask + Trading Loop)
├── .env                # Variáveis de ambiente (API keys)
├── lab_data.json       # Dados persistentes (posições, trades)
├── requirements.txt    # Dependências Python
├── templates/
│   ├── index.html      # Dashboard principal
│   ├── charts.html     # Gráficos e indicadores
│   └── performance.html # Performance e histórico
└── DOCUMENTACAO.md     # Este arquivo
```

### Threads do Sistema:

```
┌─────────────────────────────────────────────────┐
│                   MAIN PROCESS                   │
├─────────────────────────────────────────────────┤
│  Thread 1: Flask Server (porta 5000)            │
│  Thread 2: Trading Loop (análise contínua)      │
│  Thread 3: Telegram Bot (polling)               │
└─────────────────────────────────────────────────┘
```

### Fluxo de Trading:

```
1. Atualiza saldo USDT
2. Para cada moeda na WATCHLIST:
   a. Busca preço, RSI, Bollinger Bands
   b. Se SEM POSIÇÃO:
      - Verifica sinal de COMPRA
      - Se RSI < 35 E Preço <= BB_Lower → COMPRA
   c. Se COM POSIÇÃO:
      - Verifica sinal de VENDA
      - Se lucro + RSI ok → VENDE
      - Se prejuízo >= 3% → STOP LOSS
3. Atualiza dashboard
4. Aguarda 2 segundos
5. Repete
```

---

## 🔧 Histórico de Correções (15/12/2024)

### Bug 1: Saldo BRL vs USDT
**Problema:** Bot usava BRL como saldo quando BRL > USDT numericamente
**Correção:** Sempre usa USDT como `real_balance`

### Bug 2: Venda Precipitada (XRP)
**Problema:** Vendeu XRP com prejuízo -2.49% e RSI = 4
**Causa:** Stop Loss era -2.5% e não verificava RSI
**Correção:** 
- Stop Loss agora é -3%
- Bloqueio de venda se RSI < 40
- Dupla verificação antes de executar venda

### Bug 3: Compra Automática Não Funcionava
**Problema:** Bot não comprava mesmo com sinal positivo
**Causa:** Saldo era atualizado DEPOIS de verificar sinais
**Correção:** Saldo atualizado ANTES de verificar sinais

### Bug 4: Entry Price Incorreto na Venda
**Problema:** Mensagem de venda mostrava "Lucro: +0.0%"
**Causa:** `strategy['position']` era limpo ANTES de calcular lucro
**Correção:** Salva entry_price ANTES de limpar posição

### Melhorias Implementadas:
- ✅ Mensagem de COMPRA completa (preço, qty, total, RSI)
- ✅ Mensagem de VENDA completa (compra, venda, lucro %, lucro $)
- ✅ Logs detalhados antes de cada venda
- ✅ Alerta Telegram ANTES de executar venda
- ✅ Dados de lucro salvos no histórico de trades

---

## 📊 Taxas e Custos

```
Taxa Binance: 0.1% por operação
Compra + Venda = 0.2% total

Exemplo com $10:
- Compra: $10 - $0.01 = $9.99 efetivo
- Venda: $10 - $0.01 = $9.99 recebido
- Custo total: $0.02 (0.2%)

Para ter lucro líquido positivo:
- Lucro bruto mínimo: > 0.2%
- Recomendado: > 1.5% para compensar taxas
```

---

## 🚀 Como Executar

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar .env com suas chaves

# 3. Executar
python server.py

# 4. Acessar dashboard
http://localhost:5000
```

---

## ⚠️ Avisos Importantes

1. **Trading envolve riscos** - Use apenas capital que pode perder
2. **Teste primeiro** - Use valores pequenos para validar
3. **Monitore regularmente** - Bot não substitui supervisão humana
4. **API keys** - Nunca compartilhe suas chaves

---

*Documentação gerada em 15/12/2024*
*Versão do Bot: 2.0*
