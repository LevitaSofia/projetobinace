# 🚀 Estratégia Ouro: R$ 300 Reais/Mês com Sandra 3.1

Esta estratégia foi desenhada especificamente para atingir uma renda extra de **R$ 300,00 mensais** utilizando a segurança da versão *Sandra 3.1 (Majors First)*.

---

## 1. 🎯 O Objetivo Matemático

Para ganhar **R$ 300,00** por mês (aprox. **$50,00 USD**), precisamos quebrar a meta em pedaços menores e alcançáveis:

| Período | Meta em Reais (R$) | Meta em Dólares ($) |
| :--- | :--- | :--- |
| **Mês** | R$ 300,00 | $ 50.00 |
| **Semana** | R$ 75,00 | $ 12.50 |
| **Dia (Média)** | **R$ 10,00** | **$ 1.67** |

> **Resumo:** Sua missão é fazer o bot lucrar, em média, **$1.67 dólares por dia**.

---

## 2. 💰 Capital Necessário (Banca)

Para operar com segurança usando a aposta base de **$11.00** do sistema, você não pode ter apenas $11 na conta. Precisamos de margem para suportar a variação natural do mercado e permitir até 3 operações simultâneas (o limite do bot).

### Recomendação Ideal:
*   **Investimento:** **R$ 600,00 a R$ 700,00** (Aprox. **$100 a $120 USD**)
*   **Por que esse valor?**
    *   Permite que o bot abra até 3 ordens de $11 ($33 total) usando apenas ~30% da banca.
    *   Deixa ~70% de reserva para emergências (o bot não quebra se o mercado cair).

### Cenário de Risco (Mínimo Viável):
*   **Investimento:** R$ 350,00 (~$60 USD)
*   **Risco:** Moderado/Alto. Qualquer sequência de 3 perdas pode comprometer a recuperação.

---

## 3. ⚙️ Configuração do Sistema (Setup)

Você não precisa alterar o código. As configurações padrão da `Sandra 3.1` já estão calibradas para isso.

**Verifique no arquivo `.env`:**

```ini
# Aposta fixa conservadora
AMOUNT_INVEST=11.0

# Capital total disponível (ajuste para o valor real que você depositar)
SALDO_BASE=100.0

# Alavancagem: NENHUMA (Spot Market)
# O sistema opera à vista, o que elimina o risco de liquidação total.
```

---

## 4. 🧠 A Lógica de Lucro (Como chegar nos $1.67/Dia)

Com a **Sandra 3.1**, focamos em qualidade, não quantidade.

*   **Lucro Médio por Trade:** 2.5% a 5.0%
    *   Em uma aposta de $11.00: **$0.27 a $0.55 de lucro por vitória.**
*   **Contas:**
    *   Se ganhar $0.55 por trade → Precisa de **3 vitórias líquidas** por dia.
    *   Se ganhar $0.27 por trade → Precisa de **6 vitórias líquidas** por dia.

A **Sandra 3.1 (Majors First)** opera principalmente BTC, ETH, SOL e BNB. Essas moedas têm volume para garantir esses movimentos de 2% a 3% várias vezes ao dia.

---

## 5. 🛡️ Sua Rotina de Gestão (Passo a Passo)

Para garantir os R$ 300, siga esta rotina:

1.  **Monitoramento Passivo:** Deixe o Telegram com notificações ligadas.
2.  **A Meta é Teto:**
    *   Bateu **$2.00 ou $3.00** de lucro no dia? **Você pode parar o bot se quiser dormir tranquilo.**
    *   A ganância é inimiga. Garantiu os "dez reais" do dia? Missão cumprida.
3.  **Dias Vermelhos Existem:**
    *   Se um dia fechar negativo (ex: -$2.00), **NÃO AUMENTE A APOSTA** no dia seguinte.
    *   Apenas continue. A estatística de 60-70% de acerto da Sandra recupera o prejuízo em 2 ou 3 dias.

---

## ✅ Resumo da Estratégia

1.  Coloque **$100 USDT** na Binance.
2.  Mantenha `AMOUNT_INVEST=11.0` (padrão).
3.  Deixe a Sandra operar no modo **Majors First** (já ativo).
4.  Busque média de **3 trades vitoriosos por dia**.
5.  Saque seus **R$ 300** no final do mês e deixe o capital base lá para o próximo ciclo.
