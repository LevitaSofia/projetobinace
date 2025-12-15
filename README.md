# 🤖 Trading Bot Binance

Bot de trading automático para Binance com estratégia baseada em RSI e Bandas de Bollinger.

## 📁 Estrutura do Projeto

```
projetobinace/
├── server.py              # 🔧 Código principal do bot
├── .env                   # 🔐 Configurações (API keys, Telegram)
├── requirements.txt       # 📦 Dependências Python
├── lab_data.json          # 💾 Dados persistentes (posições, histórico)
├── sistema_trading.log    # 📝 Log do sistema
├── iniciar_sistema.bat    # ▶️ Iniciar o bot
├── parar_sistema.bat      # ⏹️ Parar o bot
├── rodar_escondido.vbs    # 🔇 Rodar em background (sem janela)
└── templates/
    ├── index.html         # 🏠 Página principal
    ├── charts.html        # 📊 Gráficos e análise
    └── performance.html   # 📈 Histórico de trades
```

## 🚀 Como Usar

### Iniciar o Bot
```batch
iniciar_sistema.bat
```
Ou para rodar em background (sem janela):
```batch
rodar_escondido.vbs
```

### Parar o Bot
```batch
parar_sistema.bat
```

### Acessar Interface
- **Dashboard:** http://localhost:5000
- **Gráficos:** http://localhost:5000/charts
- **Performance:** http://localhost:5000/performance

## 📊 Estratégia de Trading

O bot usa uma estratégia conservadora com **duas condições obrigatórias**:

1. **RSI < 35** (indicador de sobrevenda)
2. **Preço ≤ Banda de Bollinger Inferior + 1%**

### Saída (Venda)
- Take Profit: 4% de lucro
- Stop Loss: -2.5%
- RSI > 70 com lucro positivo

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

## ⚙️ Configuração (.env)

```env
BINANCE_API_KEY=sua_api_key
BINANCE_SECRET=sua_secret
TELEGRAM_TOKEN=token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
OPENAI_API_KEY=sua_key_openai
AMOUNT_INVEST=10.0
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
