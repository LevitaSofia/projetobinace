# Laboratório de Trading Híbrido 🏗️

Sistema avançado de trading automatizado que simula 3 estratégias simultaneamente e permite execução real na Binance.

## 🎯 Funcionalidades

- **3 Estratégias em Paralelo:**
  - 🛡️ Conservador (RSI<30 + Banda de Bollinger)
  - 🚀 Agressivo (RSI<45 + Banda de Bollinger)
  - 🎯 RSI Puro (RSI<30)

- **Modo Laboratório:** Testa com saldo fictício ($100 cada)
- **Modo Real:** Executa ordens reais na Binance
- **Dashboard ao Vivo:** Atualização a cada 2 segundos
- **Persistência:** Salva progresso em `lab_data.json`

## 📦 Instalação

```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

Crie um arquivo `.env`:

```env
BINANCE_API_KEY=sua_chave_aqui
BINANCE_SECRET=seu_secret_aqui
```

## 🚀 Execução

```bash
python server.py
```

Acesse: **http://localhost:5000**

## 🔒 Segurança

- Nunca commite o arquivo `.env`
- Use chaves API apenas com permissão de leitura/trading
- Comece sempre no modo laboratório

## 📊 Lógica das Estratégias

### Entrada
- **Conservador:** RSI < 30 E Preço < Banda Inferior
- **Agressivo:** RSI < 45 E Preço < Banda Inferior  
- **RSI Puro:** RSI < 30

### Saída
- Lucro > 1.5% OU Stop Loss < -1.5% OU RSI > 70

## 📝 Autor

Desenvolvido com ❤️ para trading automatizado responsável.
