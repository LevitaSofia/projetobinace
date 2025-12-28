# 📋 Ficha Técnica do Sistema (Sandra 3.1)

⚠️ **Dados Extraídos Diretamente do Código Fonte** (28/12/2025)

---

## 1. 💰 Gestão Financeira

| Parâmetro | Valor Configurado | Descrição |
| :--- | :--- | :--- |
| **Investimento Base** | `$11.00` | Valor padrão por entrada (aposta nível 1). |
| **Aposta Forte** | `$22.00` (2x Base) | Ativa quando RSI < 25 + Volume Alto. |
| **Aposta Máxima** | `$33.00` (3x Base) | Ativa quando RSI < 20 + Volume Alto + Pânico Extrem. |
| **Limite de Posições** | `3` Simultâneas | Máximo de risco exposto. |
| **Stop Loss (SL)** | `-1.2%` a `-3.0%` | Dinâmico (IA ajusta pelo ATR e Sentimento). |
| **Take Profit (TP)** | `+2.5%` a `+8.0%` | Dinâmico (Garante Risco/Retorno > 1.5). |

---

## 2. 🏛️ Estrutura de Ativos (Majors First)

### 👑 **TIER A (Realeza)**
> **Critérios:** RSI < 35 (5m) + Banda Inferior.
- **BTC/USDT**
- **ETH/USDT**
- **SOL/USDT**
- **BNB/USDT**

### 🛡️ **TIER B (Resto do Mercado)**
> **Critérios Extremos:** RSI < 24 (5m) + Regime BULL do BTC.
- Todas as outras moedas (DOGE, ADA, XRP, etc.)
- **Filtro Extra:** Exige Lucro Projetado > 1.2% (taxas inclusas).

---

## 3. 🛡️ Proteções de Risco

| Escudo | Gatilho | Ação |
| :--- | :--- | :--- |
| **Global Cooldown** | `60 segundos` | Impede spam de ordens sequenciais. |
| **Symbol Cooldown** | `15 minutos` | Impede comprar a mesma moeda repetidamente. |
| **Filtro DUST** | Variável (Binance) | Limpa automaticamente saldos "poeira" (< min_amount). |
| **Regime Bear** | EMA50 < EMA200 (1h) | Bloqueia compra de TIER B (Altcoins). |
| **Stop Loss Dinâmico** | `3.0%` máximo | Proteção absoluta contra dumps fortes. |

---

## 4. 🧠 Inteligência Artificial (CEO Manager)

A IA ajusta a estratégia a cada hora baseada no **Sentimento Global**:

- **🐻 Mercado BEAR (Pânico):**
  - RSI Entrada: `28` (Exige fundo extremo)
  - Stop Loss: `-2.0%` (Mais curto)
  - Modo: `DEFENSIVO`

- **🐂 Mercado BULL (Otimismo):**
  - RSI Entrada: `40` (Aceita comprar mais alto)
  - Stop Loss: `-4.5%` (Dá mais espaço para oscilar)
  - Modo: `AGRESSIVO`

---

## 5. 📞 Comunicação

- **Telegram Bot:** Ativo
- **Relatórios:** Automáticos (Vendas, Compras, Fechamento Diário)
- **API Web:** Porta `5000` (Dashboard)
