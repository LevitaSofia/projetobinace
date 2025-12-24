# 🤖 Trading Bot Binance

Bot de trading automático para Binance com estratégia baseada em RSI e Bandas de Bollinger.

Inclui:
- Multi-posições (até 3 ao mesmo tempo)
- Cálculo de lucro líquido com taxas (proteção contra “vender no 0 a 0”)
- Gráfico sob demanda via Telegram (/grafico)
- “Caçador” (CoinGecko) + “Juiz” (IA) para adicionar moedas trending com filtro de fundamentos

## 📁 Estrutura do Projeto

```
projetobinace/
├── server.py              # 🔧 Código principal do bot
├── .env                   # 🔐 Configurações (API keys, Telegram)
├── requirements.txt       # 📦 Dependências Python
├── sandra_trading.db      # 💾 Estado persistente (SQLite)
├── venv/                  # 🐍 Ambiente virtual (recomendado)
├── server.log             # 📝 Log do servidor (quando rodar via nohup)
├── server.pid             # 🧷 PID salvo (opcional, quando rodar em background)
└── templates/
    ├── index.html         # 🏠 Página principal
    ├── charts.html        # 📊 Gráficos e análise
    └── performance.html   # 📈 Histórico de trades
```

## 🚀 Como Usar

### 1) Instalar dependências

Recomendado usar ambiente virtual:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2) Configurar variáveis (.env)

Crie/edite o arquivo `.env` com suas chaves (veja exemplo abaixo).

### 3) Iniciar o servidor

Modo foreground (para debug):

```bash
./venv/bin/python3 server.py
```

Modo background (servidor “rodando sozinho”):

```bash
nohup ./venv/bin/python3 server.py > server.log 2>&1 & echo $! > server.pid
```

Parar (se você salvou o PID):

```bash
kill $(cat server.pid)
```

### Acessar Interface
- **Dashboard:** http://localhost:5000
- **Gráficos:** http://localhost:5000/charts
- **Performance:** http://localhost:5000/performance

### Endpoints de API (usados pela interface)

- `GET /api/status` — status e saldos
- `GET /api/positions` — posições abertas
- `GET /api/watchlist` — radar (RSI/preço/tendência)
- `GET /api/logs` — logs (mock/placeholder)
- `GET /api/chart/<symbol_safe>` — candles (atualmente vazio se não houver histórico)
- `POST /api/command/<cmd>` — comandos manuais (placeholder)

## 📊 Estratégia de Trading

O bot usa uma estratégia conservadora com **duas condições obrigatórias**:

1. **RSI < 35** (indicador de sobrevenda)
2. **Preço ≤ Banda de Bollinger Inferior + 1%**

### Saída (Venda)
- Take Profit: 4% de lucro
- Stop Loss: -2.5%
- RSI alto só vende se lucro mínimo cobrir taxas (configurável)

### Multi-posições
- O bot pode manter até 3 posições simultâneas (por símbolo).

## 📱 Relatórios Telegram

O bot envia relatórios automáticos via Telegram nos horários:
- 🌅 08:00
- 🌞 12:00
- 🌆 18:00
- 🌙 22:00

### Enviar Relatório Manual
```
POST http://localhost:5000/api/send_report
```

### Nota sobre /moedas
O comando `/moedas` foi ajustado para enviar um **Relatório Profissional** separando **Carteira** (posições/ativos) e **Radar** (oportunidades do mercado).

## ⚙️ Configuração (.env)

```env
BINANCE_API_KEY=sua_api_key
BINANCE_SECRET=sua_secret
TELEGRAM_TOKEN=token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
OPENAI_API_KEY=sua_key_openai
AMOUNT_INVEST=10.0

# Venda por RSI alto só se lucro (%) >= este valor
LUCRO_MINIMO_TAXAS=0.6

# Caçador (CoinGecko)
ENABLE_CACADOR=true
CACADOR_INTERVAL_S=1800
CACADOR_MAX_RANK=1000
CACADOR_MAX_NEW=5
CACADOR_MAX_JUDGE=3

# Juiz (IA)
ENABLE_JUIZ=true
JUIZ_MODEL=gpt-4o-mini
JUIZ_CACHE_TTL_S=604800
```

## 📦 Dependências

```bash
pip install -r requirements.txt
```

## 🔧 Moedas Monitoradas

- XRP/USDT
- ADA/USDT
- DOGE/USDT
- DOT/USDT
- LINK/USDT
- LTC/USDT
- SOL/USDT
- BNB/USDT
- ETH/USDT
- BTC/USDT

## ⚠️ Aviso

Este bot é para fins educacionais. Trading de criptomoedas envolve riscos significativos. Use por sua conta e risco.
