import numpy as np
from datetime import datetime, timedelta

class MarketForecaster:
    def __init__(self):
        self.fee_rate = 0.001 # 0.1% per side (BINANCE SPOT)

    def calculate_targets(self, current_price, atr, rsi, fib_levels, volatility_type="normal"):
        """
        Calcula alvos de compra e venda baseados em Fibo (Prioridade) + ATR (Fallback).
        """
        # Inicializa com ATR (Fallback)
        buy_target = current_price - (atr * 1.5)
        buy_reason = "Suporte Estatístico (1.5x ATR)"
        
        sell_target = current_price + (atr * 3.0)
        sell_reason = "Expansão de Volatilidade (3.0x ATR)"

        # 🧠 Lógica Fibo: Encontrar o suporte mais próximo (Abaixo) e resistência mais próxima (Acima)
        if fib_levels and isinstance(fib_levels, dict):
            best_support = None
            best_resistance = None
            
            # Ordena níveis para facilitar
            # Ex: {'0.236': 90000, '0.5': 88000, ...}
            # Converte valores para float para garantir
            levels = []
            for k, v in fib_levels.items():
                try: levels.append((str(k), float(v)))
                except: pass
            
            levels.sort(key=lambda x: x[1]) # Ordena pelo preço

            # Encontra níveis
            for lvl_name, price in levels:
                # Suporte: maior preço que seja MENOR que o atual (com margem de 0.2%)
                if price < current_price * 0.998:
                    if best_support is None or price > best_support[1]:
                        best_support = (lvl_name, price)
                
                # Resistência: menor preço que seja MAIOR que o atual (com margem 0.2%)
                if price > current_price * 1.002:
                    if best_resistance is None or price < best_resistance[1]:
                        best_resistance = (lvl_name, price)

            # Aplica Fibo se encontrou
            if best_support:
                buy_target = best_support[1]
                buy_reason = f"Suporte Fibo ({best_support[0]})"
            
            if best_resistance:
                sell_target = best_resistance[1]
                sell_reason = f"Resistência Fibo ({best_resistance[0]})"

        # Ajuste Fino por RSI (Se já estiver sobrevendido, compra logo)
        if rsi < 30:
            rsi_target = current_price * 0.995
            # Só muda se for mais vantajoso (comprar mais barato seria melhor, mas queremos pegar o repique)
            # Se o suporte fibo está muito longe (ex: -10%), mas rsi já é 20, usamos RSI.
            if rsi_target > buy_target:
                buy_target = rsi_target
                buy_reason = "RSI Extremo (Oportunidade Imediata)"
            
        return {
            'buy_target': buy_target,
            'buy_reason': buy_reason,
            'sell_target': sell_target,
            'sell_reason': sell_reason
        }

    def estimate_time_to_price(self, current_price, target_price, atr, adx=25, timeframe_mins=15):
        """
        Estima tempo para atingir preço baseado na 'velocidade' do preço (ATR) Ajustado pelo ADX.
        Velocidade = (ATR * SpeedFactor) / Candle
        ADX alto = Velocidade maior.
        """
        dist = abs(target_price - current_price)
        if atr <= 0: return "Indefinido"
        
        # Ajuste de velocidade pelo ADX (Trend Strength)
        # ADX 20 = 1.0x (Normal)
        # ADX 50 = 2.0x (Rápido)
        # ADX 10 = 0.5x (Lento/Lateral)
        speed_factor = max(0.2, (adx / 25.0)) 
        
        # Assume que o preço anda 0.5 ATR na direção média, multiplicado pela força da tendência
        speed_per_candle = (atr * 0.5) * speed_factor
        
        # Evita divisão por zero
        if speed_per_candle == 0: speed_per_candle = 0.0001

        candles_needed = dist / speed_per_candle
        minutes = candles_needed * timeframe_mins
        
        # Adiciona um pouco de "ruído/randomicidade" realista para não ficar sempre igual
        # (Em produção, o ADX flutua, então já muda, mas aqui garante variação no output imediato)
        # minutes = minutes * np.random.uniform(0.9, 1.1) 
        
        if minutes < 60:
            return f"{int(minutes)} min"
        else:
            hours = minutes / 60
            return f"{hours:.1f} horas"

    def simulate_trade(self, investment_usdt, entry_price, exit_price):
        """
        Simula o resultado financeiro líquido de taxas.
        """
        qty = investment_usdt / entry_price
        
        # Compra
        cost = qty * entry_price
        fee_buy = cost * self.fee_rate
        
        # Venda
        gross_return = qty * exit_price
        fee_sell = gross_return * self.fee_rate
        
        total_fees = fee_buy + fee_sell
        net_profit = gross_return - cost - total_fees
        net_pct = (net_profit / investment_usdt) * 100
        
        return {
            'investment': investment_usdt,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'gross_return': gross_return,
            'fees': total_fees,
            'net_profit': net_profit,
            'net_pct': net_pct
        }

    def generate_prediction_report(self, symbol, current_price, atr, rsi, ml_prob, fib_levels, adx=25):
        """
        Gera relatório educativo completo.
        """
        targets = self.calculate_targets(current_price, atr, rsi, fib_levels)
        
        time_to_buy = self.estimate_time_to_price(current_price, targets['buy_target'], atr, adx)
        time_to_sell = self.estimate_time_to_price(targets['buy_target'], targets['sell_target'], atr, adx)
        
        # Simula $100
        sim = self.simulate_trade(100.0, targets['buy_target'], targets['sell_target'])
        
        msg = f"🔮 *PREVISÃO EDUCACIONAL: {symbol}*\n\n"
        
        msg += f"🤖 *Análise de Inteligência Real*\n"
        msg += f"• Preço Agora: ${current_price:.4f}\n"
        msg += f"• ML Confidence: {ml_prob:.1f}% " + ("(Alta)" if ml_prob > 60 else "(Neutra)") + "\n"
        msg += f"• Tendência (ADX): {adx:.1f}\n"
        msg += f"• Volatilidade (ATR): ${atr:.4f}\n\n"
        
        msg += f"📉 *Provável Ponto de Compra*\n"
        msg += f"• Alvo: ${targets['buy_target']:.4f}\n"
        msg += f"• RSI Esperado: <30\n"
        msg += f"• Quando: Em aprox. *{time_to_buy}*\n"
        msg += f"• Por que? _{targets['buy_reason']}_\n\n"
        
        msg += f"📈 *Provável Ponto de Saída*\n"
        msg += f"• Alvo: ${targets['sell_target']:.4f}\n"
        msg += f"• RSI Esperado: >70\n"
        msg += f"• Duração do Trade: *{time_to_sell}*\n"
        msg += f"• Por que? _{targets['sell_reason']}_\n\n"
        
        msg += f"💰 *Simulação (Investindo $100)*\n"
        msg += f"• Taxas da Exchange: -${sim['fees']:.2f}\n"
        msg += f"• Lucro Líquido Previsto: *${sim['net_profit']:.2f} (+{sim['net_pct']:.2f}%)*\n"
        msg += f"\n_Lembre-se: Previsões são probabilidades, não certezas._"
        
        return msg
