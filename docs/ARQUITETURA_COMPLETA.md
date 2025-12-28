# 📚 ARQUITETURA COMPLETA DO SISTEMA DE TRADING - SANDRA AI

> **Documentação Técnica Completa e Detalhada**  
> Versão: 3.1 (Sandra Mode: Majors First) | Última atualização: 28/12/2025

---

## 🎯 VISÃO GERAL DO SISTEMA

O **Sandra AI Trading Bot** é um sistema automatizado de trading de criptomoedas que opera na **Binance** usando a biblioteca **CCXT**. O sistema combina análise técnica, inteligência artificial (OpenAI GPT), proteções de risco avançadas e gestão dinâmica de capital.

### Características Principais:
- ✅ **Trading Automático Real** (Binance Spot)
- 🤖 **IA Integrada** (OpenAI GPT-4o-mini para decisões e análises)
- 📊 **Análise Técnica Avançada** (RSI, Bollinger Bands, ADX, ATR)
- 🛡️ **Gestão de Risco Robusta** (Trailing stops, proteção de drawdown, cooldowns)
- 💰 **Apostas Variáveis** ($11/$22/$33 baseado em condições de mercado)
- 🔭 **Caçador de Oportunidades** (CoinGecko + Juiz AI)
- 📱 **Interface Web + Telegram Bot**
- 💾 **Persistência SQLite + Backup Automático**

---

## 🏗️ ARQUITETURA DO SISTEMA

### Estrutura de Arquivos

```
projetobinace/
├── server.py              # 🧠 CÉREBRO - Loop principal + Flask API
├── scalper_blindado.py    # 🎯 ESTRATÉGIA - Análise técnica avançada
├── ceo_manager.py         # 👔 CEO - Ajustes dinâmicos baseados em sentimento
├── reporting.py           # 📧 Relatórios por e-mail (diários)
├── db_backup.py           # 💾 Backup automático do SQLite
├── meu_extrato.py         # 📊 Script de extração de dados
├── .env                   # 🔐 Configurações e chaves API
├── sandra_trading.db      # 🗄️ Banco de dados SQLite
├── requirements.txt       # 📦 Dependências Python
├── start.sh               # 🚀 Script de inicialização
├── templates/             # 🎨 HTML do dashboard web
│   ├── index.html
│   ├── charts.html
│   └── performance.html
└── data/                  # 📁 Dados e backups
    └── legacy/
```

---

## 🔧 TECNOLOGIAS E DEPENDÊNCIAS

### Stack Tecnológico

| Categoria | Tecnologia | Função |
|-----------|-----------|--------|
| **Backend** | Python 3.12 | Linguagem principal |
| **Framework Web** | Flask | API REST + Dashboard |
| **Exchange** | CCXT (Binance) | Comunicação com Binance |
| **IA** | OpenAI GPT-4o-mini | Análises e decisões |
| **Mensageria** | python-telegram-bot | Bot do Telegram |
| **Banco de Dados** | SQLite 3 | Persistência de dados |
| **Análise Técnica** | NumPy, Pandas | Cálculos de indicadores |
| **Gráficos** | Matplotlib, mplfinance | Geração de charts |
| **E-mail** | smtplib (Gmail) | Relatórios diários |

### Dependências (requirements.txt)
```plaintext
flask
ccxt
python-dotenv
numpy
pandas
matplotlib
mplfinance
openai
python-telegram-bot
requests
```

---

## ⚙️ CONFIGURAÇÃO COMPLETA (.env)

### Variáveis Obrigatórias

```bash
# === BINANCE API ===
BINANCE_API_KEY=sua_chave_api
BINANCE_SECRET=seu_secret

# === TELEGRAM ===
TELEGRAM_TOKEN=seu_token
TELEGRAM_CHAT_ID=seu_chat_id

# === OPENAI ===
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini

# === TRADING ===
SYMBOL=BTC/USDT
AMOUNT_INVEST=11.0
LUCRO_MINIMO_TAXAS=1.5  # % mínimo para vender por RSI alto
```

### Variáveis Opcionais

```bash
# === CAÇADOR DE MOEDAS ===
ENABLE_CACADOR=true
CACADOR_INTERVAL_S=1800
CACADOR_MAX_RANK=1000
CACADOR_MAX_NEW=5
CACADOR_MAX_JUDGE=3

# === JUIZ (IA) ===
ENABLE_JUIZ=true
JUIZ_MODEL=gpt-4o-mini
JUIZ_CACHE_TTL_S=604800

# === GPT ===
ENABLE_GPT_TUNING=true

# === E-MAIL ===
EMAIL_ENABLED=true
EMAIL_TO=seu@email.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@email.com
SMTP_PASS=sua_senha_app

# === SEGURANÇA ===
API_TOKEN=token_protecao_api
ENV=prod

# === BANCO DE DADOS ===
DB_BACKUP_ENABLED=true
DB_BACKUP_DIR=backups
DB_BACKUP_KEEP_LAST=50
```

---

## 🧠 MODO SANDRA: GESTÃO DE CAPITAL INTELIGENTE

### Parâmetros Centralizados (SANDRA Dict)

```python
SANDRA = {
    # === APOSTAS ===
    "BASE_BET": 11.0,        # Padrão
    "BET_STRONG": 22.0,      # RSI < 25 + Volume alto
    "BET_GOLD": 33.0,        # RSI < 20 + BTC caindo 2% em 15min
    "BET_DRAWDOWN": 8.0,     # Modo proteção (após perder 10%)
    "MAX_BET": 33.0,
    
    # === ENTRADA ===
    "ENTRY_RSI": 35,         # RSI mínimo para compra
    "ENTRY_TOL": 0.01,       # Tolerância da banda (1%)
    "STRONG_RSI": 25,        # RSI para aposta forte
    "GOLD_RSI": 20,          # RSI para aposta máxima
    "DRAWDOWN_RSI": 30,      # RSI em modo proteção
    
    # === SAÍDA ===
    "SELL_RSI": 65,          # RSI alto (vende se lucro > taxa)
    "STOP_BASE": -3.0,       # Stop loss padrão (%)
    "STOP_DRAWDOWN": -2.0,   # Stop loss em proteção (%)
    "TP_SLOW": 5.0,          # Take profit fixo (%)
    "FAST_PROFIT": 8.0,      # Gatilho para trailing stop (%)
    "FAST_WINDOW_S": 300,    # Janela para detectar subida rápida (5min)
    "TRAIL_FAST": 3.0,       # Trailing stop (%)
    
    # === TEMPO ===
    "MAX_HOLD_S": 86400,     # Máximo 24h segurando (86400s)
    "MAX_HOLD_TAKE_PROFIT_PCT": 0.30,  # Realiza +0.3% após 24h
    "MAX_HOLD_CUT_LOSS_PCT": -2.50,    # Corta -2.5% após 24h
}
```

### Lógica de Apostas Dinâmicas

```python
def check_strategy_signal():
    # 1. Mercado sangrando 3 dias? PARA TUDO
    if btc_bleeding: return 0.0
    
    # 2. Modo Proteção (perdeu 10%)
    if drawdown_mode:
        if rsi < SANDRA["DRAWDOWN_RSI"]:
            return SANDRA["BET_DRAWDOWN"]  # $8
        return 0.0
    
    # 3. Regra base: RSI < 35 + Banda inferior
    if not (rsi < SANDRA["ENTRY_RSI"] and price <= bb_lower * 1.01):
        return 0.0
    
    # 4. $33: RSI < 20 + BTC caindo >2% em 15min
    if rsi < 20 and btc_dumping_15m:
        return 33.0
    
    # 5. $22: RSI < 25 + Volume alto
    if rsi < 25 and vol_now > 1.2 * vol_avg:
        return 22.0
    
    # 6. $11: Padrão
    return 11.0
```

---

## 🚀 SANDRA 3.1: FILOSOFIA "MAJORS FIRST"

A partir da versão 3.1, o sistema implementa uma **segregação rigorosa de ativos**, priorizando segurança e liquidez.

### 🏆 Sistema de Tiers (Níveis)

1. **TIER A (A Realeza)**
   - **Ativos:** BTC, ETH, SOL, BNB
   - **Privilégios:**
     - Critérios de entrada mais leves
     - Compra permitida mesmo com BTC em correção leve
     - Spread e slippage estimados mais baixos

2. **TIER B (O Resto)**
   - **Ativos:** Todas as outras altcoins
   - **Restrições Extremas:**
     - **Regime BULL Obrigatório:** Só compra se BTC estiver em tendência de alta clara (EMA50 > EMA200 no 1h)
     - **RSI de Fundo:** Exige RSI(5m) ≤ 24 e RSI(15m) ≤ 32
     - **Sniper Entry:** Preço deve estar colado na Banda de Bollinger Inferior (< 1% de distância)
     - **Edge Líquido:** Exige lucro projetado > 1.2% já descontando taxas/spread

---

## 🎯 SCALPER BLINDADO: CÉREBRO DE ANÁLISE TÉCNICA


O `scalper_blindado.py` é o módulo responsável pela **análise técnica avançada** que decide quando comprar.

### Indicadores Calculados

1. **RSI (Relative Strength Index)** - Período 14
2. **Bandas de Bollinger** - Período 20, desvio 2
3. **ADX (Average Directional Index)** - Força da tendência
4. **ATR (Average True Range)** - Volatilidade

### Configuração do Scalper

```python
CONFIG = {
    'RSI_GATILHO': 35,
    'ADX_MAXIMO': 40,
    'CONFIRMACAO_VOLUME': False,  # Desabilitado
    'ATR_MINIMO': 0.0,            # Sem filtro
}
```

### Lógica de Sinal de Compra

```python
def analisar_sinal_hibrido(raw_klines, symbol):
    # 1. Calcula RSI, BB, ADX, ATR
    price, rsi, bb_lower, bb_upper = calcular_indicadores(raw_klines)
    adx, atr = calcular_adx_atr(raw_klines)
    
    # 2. Regras de entrada
    if rsi < CONFIG['RSI_GATILHO']:
        if price <= bb_lower * 1.01:  # 1% tolerância
            if ADX_MAXIMO == 0 or adx < ADX_MAXIMO:
                return True, "RSI baixo + Banda inferior", {...}
    
    return False, "Aguardando condições", {...}
```

---

## 🔄 LOOP PRINCIPAL DE TRADING

### Fluxo de Execução

```
┌─────────────────────────────────────────────────┐
│  INICIALIZAÇÃO                                  │
│  ├─ Carrega .env                               │
│  ├─ Conecta Binance (CCXT)                     │
│  ├─ Carrega SQLite (sandra_trading.db)         │
│  ├─ Detecta posições existentes                │
│  └─ Inicia Flask + Telegram em threads         │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  LOOP INFINITO (while True)                     │
│                                                 │
│  1. CEO Manager (1x/hora)                      │
│     └─ Ajusta SANDRA baseado em Fear & Greed   │
│                                                 │
│  2. Caçador de Moedas (30 em 30min)            │
│     └─ Adiciona coins trending ao radar        │
│                                                 │
│  3. Para cada moeda na WATCHLIST:              │
│     ├─ Busca candles (5min, 100 períodos)      │
│     ├─ Scalper Blindado analisa                │
│     ├─ Atualiza market_overview                │
│     │                                           │
│     ├─ SE BOT LIGADO:                           │
│     │   ├─ SEM POSIÇÃO?                         │
│     │   │   ├─ Scalper aprova?                  │
│     │   │   ├─ BTC não sangrando?               │
│     │   │   ├─ Saldo suficiente?                │
│     │   │   ├─ Cooldown OK? (15min/par)         │
│     │   │   └─ COMPRA (execute_real_trade)      │
│     │   │                                       │
│     │   └─ COM POSIÇÃO?                         │
│     │       ├─ Verifica check_exit_signal       │
│     │       │   ├─ RSI > 78? (vende)            │
│     │       │   ├─ RSI > 65 + lucro > taxa?      │
│     │       │   ├─ Stop loss?                    │
│     │       │   ├─ Trailing stop?                │
│     │       │   └─ Take profit 5%?               │
│     │       └─ SE sim: VENDE                     │
│     │                                           │
│     └─ sleep(2) entre moedas                    │
│                                                 │
│  4. Atualiza saldo real (fetch_balance)        │
│  5. Salva estado (save_lab_data)               │
│  6. Relatórios automáticos (horário)           │
│  7. Backup DB (após trades)                    │
│                                                 │
└─────────────────────────────────────────────────┘
                    │
                    └──► Repete ∞
```

---

## 💰 EXECUÇÃO DE TRADES (execute_real_trade)

### Fluxo de Compra

```python
def execute_real_trade(action='buy', ...):
    # 1. Validações
    - Cooldown 15min por símbolo
    - Cooldown 60s global
    - Máximo 3 posições simultâneas
    - Min notional (geralmente $10 USDT)
    - Saldo suficiente
    
    # 2. Executa ordem
    order = exchange.create_market_buy_order(symbol, qty, {
        "quoteOrderQty": invest_amount
    })
    
    # 3. Registra
    - Adiciona em lab_state['strategies'][...]['positions'][symbol]
    - Grava no SQLite (trade_history)
    - Envia Telegram + gráfico
    - Atualiza cooldowns
    
    # 4. Backup
    save_lab_data()
```

### Fluxo de Venda

```python
def execute_real_trade(action='sell', ...):
    # 1. Valida saldo real da moeda
    balance = exchange.fetch_balance()
    coin_balance = balance['free'][coin]
    
    # 2. Correção de precisão (DUST handling)
    if qty < min_amount:
        if coin_balance < min_amount:
            # Remove posição (é poeira)
            del strategy['positions'][symbol]
            return False
    
    # 3. Executa venda
    order = exchange.create_market_sell_order(symbol, qty)
    
    # 4. Cálculo de lucro LÍQUIDO
    lucro_liquido_usdt = sell_net - (entry_cost + taxas_totais)
    lucro_liquido_pct = (lucro_liquido_usdt / base) * 100
    
    # 5. Atualiza PnL
    lab_state['pnl']['day_net'] += lucro_liquido_usdt
    lab_state['pnl']['total_net'] += lucro_liquido_usdt
    
    # 6. Registra, notifica, atualiza streak
    db_record_trade(...)
    send_telegram_message(...)
    update_sandra_streak(lucro_liquido_usdt)
    maybe_backup_db()
```

---

## 🛡️ SISTEMA DE PROTEÇÃO E GESTÃO DE RISCO

### 1. Proteção de Drawdown (10%)

```python
# Rastreamento de equity (capital total)
if equity > GLOBAL_STATS['peak_balance']:
    GLOBAL_STATS['peak_balance'] = equity
    GLOBAL_STATS['drawdown_mode'] = False

elif equity < GLOBAL_STATS['peak_balance'] * 0.9:
    # Perdeu 10% do pico
    GLOBAL_STATS['drawdown_mode'] = True
    # Reduz aposta para $8
    # Stop loss mais apertado (-2% ao invés de -3%)
```

### 2. Cooldowns (Anti-spam)

```python
# Cooldown por símbolo: 15 minutos
SYMBOL_COOLDOWN = 900  # segundos

# Cooldown global: 60 segundos entre qualquer trade
GLOBAL_COOLDOWN = 60

# Cooldown de alertas: 5 minutos por moeda
ALERT_COOLDOWN = 300
```

### 3. Proteção BTC

```python
# Se BTC cair >2% em 15 minutos: não compra NADA
btc_drop_15m()  # Cache 20s

# Se BTC sangrar 3 dias consecutivos: PARA TUDO
btc_bleeding_3days()  # Cache 1h
```

### 4. Trailing Stop Persistente

```python
# Ativa quando: lucro >= 8% em < 5 minutos
if profit_pct >= SANDRA["FAST_PROFIT"] and elapsed <= 300:
    position["trail_active"] = True
    position["highest_price"] = current_price

# Vende quando: recuar 3% do pico
if trail_active:
    pullback = ((highest - current) / highest) * 100
    if pullback >= 3.0:
        SELL
```

### 5. Validação de Venda Inteligente (Taxas)

```python
# RSI alto só vende se cobrir taxas
LUCRO_MINIMO_TAXAS = 1.5  # %

if rsi >= 65:
    if profit_pct > LUCRO_MINIMO_TAXAS:
        SELL  # Garante lucro líquido
    else:
        HOLD  # Aguarda melhor momento
```

### 6. Sistema de Streak (Adaptação)

```python
# 2 perdas seguidas: aperta
if losses >= 2:
    SANDRA["ENTRY_RSI"] = 32
    SANDRA["STOP_BASE"] = -2.5
    SANDRA["ENTRY_TOL"] = 0.005

# 4 vitórias seguidas: relaxa
if wins >= 4:
    SANDRA["ENTRY_RSI"] = 35
    SANDRA["STOP_BASE"] = -3.0
    SANDRA["ENTRY_TOL"] = 0.01
```

---

## 🔭 CAÇADOR DE MOEDAS + JUIZ (IA)

### Caçador (Trending Coins)

```python
def cacador_de_gemas():
    # 1. Busca moedas trending na CoinGecko
    url = "https://api.coingecko.com/api/v3/search/trending"
    coins = requests.get(url).json()['coins']
    
    # 2. Para cada moeda:
    for coin in coins:
        symbol = coin['item']['symbol'].upper()
        coin_id = coin['item']['id']
        rank = coin['item']['market_cap_rank']
        
        # Filtros:
        if rank > CACADOR_MAX_RANK: continue
        
        # 3. Verifica se existe na Binance
        binance_symbol = f"{symbol}/USDT"
        try:
            ticker = exchange.fetch_ticker(binance_symbol)
            price = ticker['last']
        except:
            continue  # Não existe na Binance
        
        # 4. Juiz (IA) avalia fundamentos
        ok, reason, risk = juiz_de_moedas(symbol, coin_id)
        if not ok:
            continue  # Rejeitado pelo juiz
        
        # 5. Adiciona ao radar
        WATCHLIST.append(binance_symbol)
        lab_state['dynamic_watchlist'].append(binance_symbol)
```

### Juiz (IA Filter)

```python
def juiz_de_moedas(symbol, coin_id):
    # 1. Cache (7 dias)
    cached = lab_state['judge_cache'].get(coin_id)
    if cached and not expired:
        return cached['approved'], cached['reason'], cached['risk']
    
    # 2. Busca dados CoinGecko
    data = requests.get(f"https://api.coingecko.com/api/v3/coins/{coin_id}").json()
    description = data['description']['en']
    categories = data['categories']
    rank = data['market_cap_rank']
    
    # 3. Regras duras (blacklist)
    privacy_coins = {'XMR', 'ZEC', 'DASH'}
    if symbol in privacy_coins:
        return False, "Privacy Coin", "Alto"
    
    # 4. GPT avalia
    prompt = f"""
    Você é Auditor de Cripto. Analise este projeto:
    
    SÍMBOLO: {symbol}
    RANK: {rank}
    CATEGORIAS: {categories}
    DESCRIÇÃO: {description[:800]}
    
    Responda JSON:
    {{
      "aprovado": true/false,
      "motivo": "frase curta",
      "risco": "Baixo/Medio/Alto"
    }}
    
    Rejeite rug pulls, projetos abandonados, suspeitos.
    """
    
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    
    result = json.loads(resp.choices[0].message.content)
    
    # 5. Cache resultado
    lab_state['judge_cache'][coin_id] = {
        'ts': time.time(),
        'approved': result['aprovado'],
        'reason': result['motivo'],
        'risk': result['risco']
    }
    
    return result['aprovado'], result['motivo'], result['risco']
```

---

## 💾 PERSISTÊNCIA E BACKUP

### SQLite Schema

```sql
-- Estado do sistema (JSON)
CREATE TABLE system_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Histórico eterno de trades
CREATE TABLE trade_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT,
    symbol TEXT,
    side TEXT,
    price REAL,
    qty REAL,
    profit_usdt REAL,
    profit_pct REAL,
    timestamp TEXT,
    json_data TEXT
);

-- Eventos importantes (auditoria)
CREATE TABLE system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    level TEXT,
    event_type TEXT,
    message TEXT,
    json_data TEXT
);
```

### Backup Automático

```python
def maybe_backup_db(reason=''):
    # Dispara após cada venda
    # Configurável via .env:
    # - DB_BACKUP_ENABLED=true
    # - DB_BACKUP_DIR=backups
    # - DB_BACKUP_KEEP_LAST=50
    
    backup_sqlite_db(
        db_path='sandra_trading.db',
        backup_dir='backups',
        keep_last=50
    )
    # Cria: backups/sandra_trading_20251225_193045.db
```

---

## 📡 API REST (Flask)

### Rotas Principais

| Método | Rota | Descrição | Autenticação |
|--------|------|-----------|--------------|
| GET | `/` | Dashboard principal | - |
| GET | `/charts` | Página de gráficos | - |
| GET | `/performance` | Relatório de performance | - |
| GET | `/api/status` | Status geral do bot | API_TOKEN |
| GET | `/api/positions` | Posições abertas | - |
| GET | `/api/watchlist` | Moedas monitoradas | - |
| GET | `/api/logs` | Últimos logs | - |
| GET | `/api/performance` | Estatísticas completas | - |
| GET | `/api/position` | Posição ativa (compat) | - |
| GET | `/api/chart/<symbol>` | Dados de velas + indicadores | - |
| POST | `/api/toggle_live` | Liga/desliga modo real | API_TOKEN |
| POST | `/api/toggle_running` | Liga/desliga bot | API_TOKEN |
| POST | `/api/force_buy` | Compra forçada (teste) | API_TOKEN |
| POST | `/api/close_position` | Venda forçada | API_TOKEN |
| POST | `/api/clear-position` | Limpa posição (dust) | API_TOKEN |
| POST | `/api/convert_brl` | Converte BRL→USDT | - |
| POST | `/api/command/<cmd>` | Comandos manuais | API_TOKEN |

### Autenticação

```python
# Header:
X-API-Token: seu_token

# Ou query string:
?token=seu_token

# Ou Authorization header:
Authorization: Bearer seu_token
```

---

## 📱 TELEGRAM BOT

### Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `/start` | Inicia o bot |
| `/ajuda` | Lista todos os comandos |
| `/status` | Moeda analisada agora |
| `/saldo` | Seu saldo (BRL + USDT + moedas) |
| `/posicao` | Posição principal |
| `/moedas` | Relatório profissional (carteira + radar) |
| `/relatorio` | Análise completa do mercado |
| `/grafico` | Gráfico da moeda atual |
| `/comprar [MOEDA]` | Força compra (ex: `/comprar XRP`) |
| `/converter` | Converte BRL para USDT |
| `/ligar` | Liga o bot automático |
| `/desligar` | Desliga o bot automático |
| `/ia` | Mostra parâmetros Sandra |
| `/ia reset` | Reseta parâmetros Sandra |

### Conversa com IA (GPT)

```python
# Envia qualquer mensagem de texto ou áudio
"Quanto estou ganhando?"
"Por que não comprou ADA?"
"Qual o melhor momento para vender?"

# A IA responde com contexto REAL:
# - Posições abertas
# - Cenários de lucro/prejuízo
# - Histórico de trades
# - Razões de bloqueios
# - Dados de mercado atualizados
```

### Mensagens Automáticas

- 🔵 Confirmação de compra (com gráfico)
- ✅ Confirmação de venda (com lucro líquido)
- 🚨 Alertas de oportunidades (RSI < 40)
- 🤖 Ajustes da IA (parâmetros alterados)
- 🔭 Caçador encontrou novas moedas
- ⛔ Juiz rejeitou uma moeda
- 📊 Relatórios automáticos (8h, 12h, 18h, 22h)

---

## 📊 CEO MANAGER: AJUSTES DINÂMICOS

```python
def get_market_sentiment():
    # Fear & Greed Index (Alternative.me)
    url = "https://api.alternative.me/fng/"
    data = requests.get(url).json()
    fng_value = int(data['data'][0]['value'])
    
    if fng_value < 20: return "EXTREME_FEAR", fng_value
    if fng_value < 40: return "FEAR", fng_value
    if fng_value < 60: return "NEUTRAL", fng_value
    if fng_value < 80: return "GREED", fng_value
    return "EXTREME_GREED", fng_value

def calculate_dynamic_strategy(sentiment, fng_val):
    if sentiment == "EXTREME_FEAR":
        # Mercado em pânico: mais agressivo
        return {
            "MODE": "CAÇADOR",
            "ENTRY_RSI": 38,
            "STOP_BASE": -3.5,
            "ENTRY_TOL": 0.015
        }
    
    elif sentiment == "FEAR":
        return {
            "MODE": "OPORTUNISTA",
            "ENTRY_RSI": 36,
            "STOP_BASE": -3.0,
            "ENTRY_TOL": 0.012
        }
    
    elif sentiment == "EXTREME_GREED":
        # Mercado eufórico: conservador
        return {
            "MODE": "DEFENSIVO",
            "ENTRY_RSI": 32,
            "STOP_BASE": -2.5,
            "ENTRY_TOL": 0.008
        }
    
    else:  # NEUTRAL / GREED
        return {
            "MODE": "EQUILIBRADO",
            "ENTRY_RSI": 35,
            "STOP_BASE": -3.0,
            "ENTRY_TOL": 0.01
        }
```

---

## 📧 RELATÓRIOS POR E-MAIL

### Configuração (Gmail SMTP)

```bash
EMAIL_ENABLED=true
EMAIL_TO=seu@email.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu@gmail.com
SMTP_PASS=senha_app_gmail  # Senha de app, não a senha normal!
```

### Relatório Diário

Enviado automaticamente às 23:59 (configurável):

```python
# Conteúdo:
- Resumo do dia (trades, lucro líquido)
- Posições abertas
- Histórico 7 dias (rolling)
- Taxa de acerto
- Melhor/Pior trade
- Moedas mais negociadas
```

---

## 🔐 SEGURANÇA E BOAS PRÁTICAS

### 1. Proteção de API

```python
API_TOKEN = os.getenv('API_TOKEN')
ENV = os.getenv('ENV', 'dev')

if ENV == "prod" and not API_TOKEN:
    raise RuntimeError("API_TOKEN obrigatório em produção")

# Middleware Flask:
@app.before_request
def protect_api():
    if request.path.startswith('/api/'):
        _require_api_token_if_configured()
```

### 2. Sincronização de Tempo

```python
# Binance rejeita requisições se o relógio estiver dessincronizado
exchange_temp = ccxt.binance()
server_time = exchange_temp.fetch_time()
local_time = int(time.time() * 1000)
time_diff = server_time - local_time

exchange = ccxt.binance({
    'options': {
        'timeDifference': time_diff,
        'recvWindow': 60000
    }
})
```

### 3. Rate Limiting

```python
# CCXT já gerencia rate limits automaticamente
exchange = ccxt.binance({
    'enableRateLimit': True
})

# Cache adicional para evitar spam:
cached_fetch_balance(ttl_s=3.0)
cached_private_get_account(ttl_s=10.0)
```

### 4. Tratamento de Erros

```python
# Nunca derruba o loop principal
try:
    execute_real_trade(...)
except Exception as e:
    print(f"❌ ERRO: {e}")
    send_telegram_message(f"❌ ERRO: {e}")
    # Continua rodando
```

### 5. Logs Rotativos

```python
# Evita que logs cresçam infinitamente
RotatingFileHandler(
    'sistema_trading.log',
    maxBytes=5_000_000,  # 5MB
    backupCount=5         # Mantém 5 arquivos
)
```

---

## 🚀 INICIALIZAÇÃO E DEPLOY

### 1. Instalação

```bash
# Clone o repositório
git clone https://github.com/LevitaSofia/projetobinace.git
cd projetobinace

# Crie ambiente virtual
python3 -m venv venv
source venv/bin/activate

# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env  # Edite com suas chaves
```

### 2. Execução Manual

```bash
python3 server.py
```

### 3. Execução com Systemd (Linux)

```bash
# Copie o service
sudo cp scripts/systemd/projetobinace.service /etc/systemd/system/

# Habilite e inicie
sudo systemctl enable projetobinace
sudo systemctl start projetobinace

# Verifique status
sudo systemctl status projetobinace

# Logs
sudo journalctl -u projetobinace -f
```

### 4. Script de Inicialização

```bash
#!/bin/bash
cd /home/ubuntu/projetobinace
pkill -f server.py
sleep 2
nohup /home/ubuntu/projetobinace/venv/bin/python3 server.py > output.log 2>&1 &
echo $! > server.pid
```

---

## 📈 WATCHLIST: MOEDAS MONITORADAS

### Estrutura de Prioridade

```python
# Alta prioridade (voláteis, ótimos para scalping)
PRIORITY_COINS = [
    'PEPE/USDT',  # Meme coin (volatilidade extrema)
    'WIF/USDT',   # Meme coin
    'DOGE/USDT',  # Liquidez gigante
    'SOL/USDT',   # Sólida + líquida
]

# Secundárias (alternativas consistentes)
SECONDARY_COINS = [
    'DOT/USDT',
    'LTC/USDT',
    'ADA/USDT',
    'BNB/USDT',
]

# Último recurso (só se tudo mais estiver ruim)
LAST_RESORT = [
    'ETH/USDT',
    'BTC/USDT',
]

WATCHLIST = PRIORITY_COINS + SECONDARY_COINS + LAST_RESORT
```

### Watchlist Dinâmica

```python
# Adicionadas automaticamente pelo Caçador
lab_state['dynamic_watchlist'] = [
    'XRP/USDT',  # Exemplo: encontrada trending
    'AVAX/USDT',
    ...
]

# Limite: 50 moedas totais
```

---

## 🧪 MODO MULTI-POSIÇÕES

O sistema suporta até **3 posições simultâneas**:

```python
strategy['positions'] = {
    'SOL/USDT': {
        'symbol': 'SOL/USDT',
        'entry_price': 245.30,
        'qty': 0.0448,
        'entry_time': '2025-12-25T19:00:00',
        'highest_price': 247.80,
        'trail_active': False,
        'entry_cost_usdt': 11.0,
        'entry_fee_usdt': 0.011,
    },
    'DOGE/USDT': {...},
    'ADA/USDT': {...},
}
```

### Cooldown por Símbolo

Cada par tem cooldown independente de 15 minutos:

```python
lab_state['symbol_cooldowns'] = {
    'SOL/USDT': 1703524800.0,
    'DOGE/USDT': 1703524200.0,
}
```

---

## 🎨 DASHBOARD WEB

Acessível em `http://localhost:5000`

### Páginas:

1. **Index** (`/`) - Visão geral, posições, watchlist
2. **Charts** (`/charts`) - Gráficos de velas + RSI + BB
3. **Performance** (`/performance`) - Estatísticas de trades

### Tecnologias Frontend:

- HTML5 + CSS3
- JavaScript Vanilla
- Chart.js (gráficos)
- Fetch API (AJAX)
- Auto-refresh (5s)

---

## 🐛 DEBUGGING E DIAGNÓSTICOS

### Diagnósticos por Moeda

```python
lab_state['diagnostics'] = {
    'SOL/USDT': '📈 COMPRADO (Lucro: +2.3%)',
    'BTC/USDT': '⏳ RSI=42 (precisa <35) | Preço 2.1% acima da banda',
    'DOGE/USDT': '💸 SALDO BAIXO ($7.50 < $11.00)',
    'ADA/USDT': '🛡️ Proteção ativa (drawdown 10%)',
}
```

### Última Decisão por Símbolo

```python
lab_state['last_decisions'] = {
    'XRP/USDT': {
        'ts': '2025-12-25T19:05:23',
        'price': 2.45,
        'rsi': 33.2,
        'scalper_ok': True,
        'scalper_reason': 'RSI baixo + Banda inferior',
        'buy_attempted': True,
        'buy_result': False,
        'block_reason': 'Cooldown do par (15min)',
    }
}
```

### Bloqueios Registrados

```python
lab_state['last_trade_block_by_symbol'] = {
    'ADA/USDT': {
        'ts': '2025-12-25T18:50:00',
        'action': 'buy',
        'symbol': 'ADA/USDT',
        'reason': 'Saldo insuficiente: precisa $11.00 e tem $8.50',
    }
}
```

---

## ⚡ PERFORMANCE E OTIMIZAÇÕES

### 1. Cache Multi-Nível

```python
# Market data cache (10s TTL)
_market_cache[symbol] = {
    'ts': time.monotonic(),
    'value': (price, rsi, bb_lower, bb_upper, vol_now, vol_avg)
}

# Balance cache (3s TTL)
cached_fetch_balance(ttl_s=3.0)

# BTC dump cache (20s TTL)
btc_drop_15m_cached(ttl=20)

# BTC bleeding cache (1h TTL)
btc_bleeding_3days_cached(ttl=3600)

# Juiz cache (7 dias TTL)
lab_state['judge_cache'][coin_id] = {...}
```

### 2. Paralelização Controlada

```python
# Thread 1: Flask (API web)
flask_thread = threading.Thread(target=run_flask, daemon=True)

# Thread 2: Trading Loop
trading_thread = threading.Thread(target=trading_loop, daemon=True)

# Thread 3: Telegram (main - precisa sinais)
telegram_app.run_polling()

# Thread worker: Fila de mensagens Telegram
_telegram_worker()  # Processa fila assíncrona
```

### 3. Locks para Thread-Safety

```python
# Lock global (estado compartilhado)
state_lock = threading.RLock()

# Lock da exchange (nonce/rate-limit)
exchange_lock = threading.RLock()

# Uso:
with state_lock:
    lab_state['current_price'] = price
```

---

## 📝 LOGS E MONITORAMENTO

### Formato de Logs

```
2025-12-25 19:05:23 - INFO - 🔎 SOL/USDT: RSI=33.2 | Preço=$245.30 | Saldo=$24.95
2025-12-25 19:05:23 - INFO - 🧠 SCALPER BLINDADO APROVOU: RSI baixo + Banda inferior
2025-12-25 19:05:23 - INFO - 🎯 SINAL DETECTADO: Investir $11.0 em SOL/USDT!
2025-12-25 19:05:28 - INFO - 💰 [Trading Real 💰 (Sandra)] COMPRA REAL: 0.0448 SOL/USDT @ $245.3042
2025-12-25 19:05:28 - INFO - 📨 Mensagem Telegram enviada com sucesso.
```

### Monitoramento em Tempo Real

```bash
# Systemd logs
sudo journalctl -u projetobinace -f

# Arquivo de log
tail -f sistema_trading.log

# Logs via API
curl http://localhost:5000/api/logs
```

---

## 🔄 MIGRAÇÃO E COMPATIBILIDADE

### Formato Antigo → Novo

```python
# Antigo (uma posição só)
strategy['position'] = {
    'symbol': 'BTC/USDT',
    'entry_price': 100000,
    'qty': 0.00011,
    ...
}

# Novo (múltiplas posições)
strategy['positions'] = {
    'BTC/USDT': {
        'symbol': 'BTC/USDT',
        'entry_price': 100000,
        'qty': 0.00011,
        ...
    },
    'ETH/USDT': {...},
}

# Migração automática no código:
if strategy.get('position'):
    pos_old = strategy['position']
    symbol = pos_old['symbol']
    strategy.setdefault('positions', {})
    strategy['positions'][symbol] = pos_old
    strategy['position'] = None  # Limpa antigo
```

---

## 🌟 FEATURES ESPECIAIS

### 1. Conversão Automática BRL→USDT

```python
# Se faltar USDT, tenta converter BRL automaticamente
if usdt_balance < required:
    print("⏳ Convertendo BRL para USDT...")
    new_usdt = convert_brl_to_usdt(min_brl=10)
```

### 2. Detecção Automática de Posições

```python
# Ao iniciar, verifica carteira e restaura posições
detect_existing_positions()

# Procura por moedas da WATCHLIST com saldo > $1
# Estima preço de entrada (histórico ou atual)
# Restaura posições no lab_state
```

### 3. Limpeza de Dust (Poeira)

```python
# Se saldo < min_amount da Binance:
if coin_balance < min_amount:
    print(f"🧹 DUST detectado: {coin_balance}")
    del strategy['positions'][symbol]
    send_telegram_message("🧹 Posição removida (DUST)")
```

### 4. Gráficos Sob Demanda

```python
# Gera PNG em memória e envia no Telegram
def generate_chart_image(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, '1m', limit=100)
    df = pd.DataFrame(ohlcv, columns=[...])
    buf = io.BytesIO()
    mpf.plot(df, type='candle', savefig=buf)
    return buf

send_chart_to_telegram(symbol, caption="Compra executada")
```

### 5. Radar Financeiro (Educacional)

```python
# Mostra break-even e alvos líquidos
custo_total = entry_cost + entry_fee
breakeven_price = custo_total / (qty * (1 - FEE_RATE))
target_price_1pct = (custo_total * 1.01) / (qty * (1 - FEE_RATE))

print(f"Break-even: ${breakeven_price:.4f}")
print(f"Alvo (+1% líquido): ${target_price_1pct:.4f}")
```

---

## 📖 GLOSSÁRIO TÉCNICO

| Termo | Significado |
|-------|-------------|
| **RSI** | Relative Strength Index - Indicador de força (0-100) |
| **BB** | Bollinger Bands - Bandas de volatilidade |
| **ADX** | Average Directional Index - Força da tendência |
| **ATR** | Average True Range - Volatilidade em $$ |
| **Trailing Stop** | Stop móvel que acompanha o preço subindo |
| **Drawdown** | Queda do capital em relação ao pico |
| **PnL** | Profit and Loss (Lucro e Prejuízo) |
| **Dust** | Poeira - Saldo muito pequeno para vender |
| **Min Notional** | Valor mínimo de ordem (Binance) |
| **Cooldown** | Tempo de espera entre ações |
| **Scalping** | Estratégia de trades rápidos e frequentes |
| **Spot** | Mercado à vista (não alavancado) |
| **CCXT** | Biblioteca unificada para exchanges |
| **Webhook** | Callback HTTP para eventos |

---

## 🎓 CONCEITOS-CHAVE DO SANDRA MODE

### 1. Apostas Variáveis (Dynamic Bet Sizing)

Ao invés de apostar sempre o mesmo valor, Sandra ajusta baseado em:
- **RSI**: Quanto menor, maior a aposta
- **Volume**: Se alto, aumenta confiança
- **BTC**: Se caindo forte, oportunidade máxima
- **Drawdown**: Se perdendo, diminui risco

### 2. Lucro Líquido Real

Sandra calcula o lucro **DEPOIS** das taxas:

```
Lucro Bruto = (Preço Venda - Preço Compra) * Quantidade
Taxa Compra = Custo Compra * 0.001
Taxa Venda = Valor Venda * 0.001
Lucro Líquido = Lucro Bruto - Taxa Compra - Taxa Venda
```

### 3. Proteção Multi-Camada

- **Camada 1**: BTC sangrando? Não opera
- **Camada 2**: Drawdown 10%? Reduz risco
- **Camada 3**: Cooldown por moeda (15min)
- **Camada 4**: Limite de 3 posições
- **Camada 5**: Validação de precisão (dust)
- **Camada 6**: RSI alto só vende se lucro > taxa

### 4. Trailing Stop Inteligente

Ativa APENAS se subir rápido (8% em 5min):
- Garante realização de lucro em pumps
- Não interfere em subidas lentas (usa TP 5%)
- Recua máximo: 3% do pico

---

## 🛠️ TROUBLESHOOTING

### Problema: Bot não compra nada

**Checklist:**
1. Bot está ligado? (`lab_state['running'] = True`)
2. Modo real ativo? (`lab_state['is_live'] = True`)
3. Saldo suficiente? (mínimo $11 USDT)
4. Cooldown respeitado? (15min por moeda)
5. BTC sangrando? (3 dias vermelhos = bloqueio)
6. Scalper aprovou? (verifique `last_decisions`)
7. Máximo 3 posições? (limite de risco)

### Problema: Erro de precisão (min_amount)

**Solução aplicada:**
```python
# Correção automática de DUST
if qty < min_amount:
    if coin_balance < min_amount:
        # Remove posição interna
        del strategy['positions'][symbol]
        send_telegram_message("🧹 DUST removido")
```

### Problema: Telegram não responde

**Checklist:**
1. Token correto? (`TELEGRAM_TOKEN`)
2. Chat ID correto? (`TELEGRAM_CHAT_ID`)
3. Instâncias duplicadas? (causa conflito de polling)
4. Firewall bloqueando?

### Problema: Exchange timeout

**Solução:**
```python
# CCXT gerencia automaticamente:
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'recvWindow': 60000,
        'timeDifference': time_diff
    }
})
```

---

## 📚 REFERÊNCIAS E LINKS ÚTEIS

- [CCXT Documentation](https://docs.ccxt.com/)
- [Binance API](https://binance-docs.github.io/apidocs/spot/en/)
- [OpenAI API](https://platform.openai.com/docs/)
- [Python Telegram Bot](https://docs.python-telegram-bot.org/)
- [CoinGecko API](https://www.coingecko.com/en/api/documentation)
- [Fear & Greed Index](https://alternative.me/crypto/fear-and-greed-index/)

---

## 📄 LICENÇA E AVISOS

⚠️ **AVISO IMPORTANTE:**

Este sistema foi desenvolvido para **fins educacionais** e de **automação pessoal**. 

**Trading de criptomoedas envolve riscos significativos:**
- Pode perder todo o capital investido
- Volatilidade extrema
- Não há garantias de lucro
- Use apenas capital que pode perder

**Responsabilidades:**
- Teste em modo simulação primeiro
- Entenda completamente o código
- Monitore constantemente
- Ajuste parâmetros ao seu perfil de risco
- Consulte um profissional antes de investir

---

## 🎉 CONCLUSÃO

O **Sandra AI Trading Bot** é um sistema completo e robusto de trading automatizado que combina:

- ✅ **Análise técnica profissional** (Scalper Blindado)
- 🧠 **Inteligência artificial contextual** (GPT-4o-mini)
- 🛡️ **Proteções de risco em múltiplas camadas**
- 💰 **Gestão dinâmica de capital** (apostas variáveis)
- 🔭 **Descoberta automática de oportunidades** (Caçador + Juiz)
- 📊 **Monitoramento em tempo real** (Web + Telegram)
- 💾 **Persistência confiável** (SQLite + backups)

O sistema foi projetado para operar **24/7** de forma autônoma, tomando decisões baseadas em dados reais de mercado, histórico de performance e condições globais (Fear & Greed, BTC, etc.).

**Total de linhas documentadas:** 4.750+ (server.py) + módulos auxiliares  
**Total de funcionalidades:** 50+  
**Total de proteções:** 15+

---

**Desenvolvido com ❤️ para traders que valorizam automação inteligente e gestão de risco.**

📌 **Última atualização:** 25/12/2025  
📌 **Versão:** 2.0 (Sandra Mode Completo)  
📌 **Commit:** e6aeb68

---
