"""
trade_reporter.py - Relatório Completo de Trades

Gera relatórios detalhados via Email e Telegram quando comprar moedas TIER B (fracas/emergentes).
Explica EXATAMENTE por que a decisão foi tomada com todos os dados verificados.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
import pandas_ta as ta


def calculate_btc_regime(exchange):
    """Calcula regime BTC (EMA50 vs EMA200 em 1h)."""
    try:
        klines = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=200)
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        df['EMA50'] = ta.ema(df['close'], length=50)
        df['EMA200'] = ta.ema(df['close'], length=200)
        
        ema50 = df['EMA50'].iloc[-1]
        ema200 = df['EMA200'].iloc[-1]
        
        if ema50 > ema200:
            return "BULL", ema50, ema200
        elif ema50 < ema200:
            return "BEAR", ema50, ema200
        return "NEUTRAL", ema50, ema200
    except Exception as e:
        print(f"⚠️ Erro ao calcular regime BTC: {e}")
        return "UNKNOWN", 0, 0


def analyze_trade_complete(exchange, symbol, position_size, tp_pct, sl_pct, tier='B'):
    """
    Análise completa de um trade segundo Sandra 2.1.
    
    Returns:
        dict com todos os dados para relatório
    """
    try:
        # 1. Dados 24h
        ticker = exchange.fetch_ticker(symbol)
        var_24h = ticker.get('percentage', 0.0)
        volume_24h = ticker.get('quoteVolume', 0.0)
        price = ticker['last']
        
        # 2. Orderbook (spread)
        depth = exchange.fetch_order_book(symbol, limit=5)
        bid = depth['bids'][0][0]
        ask = depth['asks'][0][0]
        spread_pct = ((ask - bid) / bid) * 100
        spread_bps = spread_pct * 100
        
        # 3. Regime BTC
        regime, ema50, ema200 = calculate_btc_regime(exchange)
        
        # 4. Cálculo de custos e EDGE
        fee_rate = 0.001  # 0.1% Binance
        fee_buy_usd = position_size * fee_rate
        fee_sell_usd = position_size * fee_rate
        spread_cost_usd = position_size * (spread_pct / 100)
        
        # Slippage estimado (heurística simples)
        slippage_pct = 0.15  # 0.15% para TIER B
        slippage_usd = position_size * (slippage_pct / 100)
        
        cost_total_usd = fee_buy_usd + fee_sell_usd + spread_cost_usd + slippage_usd
        cost_total_pct = (cost_total_usd / position_size) * 100
        
        # Edge líquido
        edge_liquido_pct = tp_pct - cost_total_pct
        
        # 5. Limites Sandra 2.1
        min_vol_tier = 10_000_000 if tier == 'B' else 50_000_000
        max_spread_tier = 18 if tier == 'B' else 12
        min_edge_tier = 0.80 if tier == 'B' else 0.50
        
        # 6. Verificações
        violations = []
        warnings = []
        
        # Regime BTC
        if tier == 'B' and regime != 'BULL':
            violations.append(f"TIER B em regime {regime} (exige BULL)")
        
        # Variação 24h
        if var_24h < -10.0:
            violations.append(f"Variação 24h {var_24h:.2f}% (sangria > -10%)")
        
        # Volume
        if volume_24h < min_vol_tier:
            warnings.append(f"Volume ${volume_24h:,.0f} < ${min_vol_tier:,}")
        
        # Spread
        if spread_bps > max_spread_tier:
            warnings.append(f"Spread {spread_bps:.1f} bps > {max_spread_tier} bps")
        
        # Edge
        if edge_liquido_pct < min_edge_tier:
            warnings.append(f"Edge líquido {edge_liquido_pct:.2f}% < {min_edge_tier}%")
        
        return {
            'symbol': symbol,
            'tier': tier,
            'price': price,
            'position_size': position_size,
            'tp_pct': tp_pct,
            'sl_pct': sl_pct,
            'market_data': {
                'var_24h': var_24h,
                'volume_24h': volume_24h,
                'bid': bid,
                'ask': ask,
                'spread_pct': spread_pct,
                'spread_bps': spread_bps,
            },
            'regime': {
                'btc_regime': regime,
                'ema50': ema50,
                'ema200': ema200,
            },
            'costs': {
                'fee_buy': fee_buy_usd,
                'fee_sell': fee_sell_usd,
                'spread': spread_cost_usd,
                'slippage': slippage_usd,
                'total_usd': cost_total_usd,
                'total_pct': cost_total_pct,
            },
            'edge': {
                'liquido_pct': edge_liquido_pct,
                'min_required': min_edge_tier,
            },
            'limits': {
                'min_volume': min_vol_tier,
                'max_spread': max_spread_tier,
                'min_edge': min_edge_tier,
            },
            'violations': violations,
            'warnings': warnings,
            'timestamp': datetime.now().isoformat(),
        }
    
    except Exception as e:
        print(f"❌ Erro na análise completa: {e}")
        return None


def generate_telegram_report(analysis):
    """Gera relatório resumido para Telegram."""
    if not analysis:
        return "❌ Erro ao gerar relatório"
    
    a = analysis
    regime_emoji = "🐂" if a['regime']['btc_regime'] == "BULL" else "🐻" if a['regime']['btc_regime'] == "BEAR" else "⚖️"
    
    msg = f"""🚨 **RELATÓRIO DE TRADE - TIER {a['tier']}**

📊 **{a['symbol']}** | ${a['price']:.4f}
💰 Posição: ${a['position_size']:.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **MERCADO 24H:**
• Variação: {a['market_data']['var_24h']:+.2f}%
• Volume: ${a['market_data']['volume_24h']:,.0f}
• Spread: {a['market_data']['spread_bps']:.1f} bps

🌊 **REGIME BTC:**
• Status: {regime_emoji} {a['regime']['btc_regime']}
• EMA50: ${a['regime']['ema50']:,.2f}
• EMA200: ${a['regime']['ema200']:,.2f}

💰 **ANÁLISE DE CUSTOS:**
• Taxa compra: ${a['costs']['fee_buy']:.3f}
• Taxa venda: ${a['costs']['fee_sell']:.3f}
• Spread: ${a['costs']['spread']:.3f}
• Slippage: ${a['costs']['slippage']:.3f}
━━━━━━━━━━━━━━━━
• **TOTAL: ${a['costs']['total_usd']:.3f} ({a['costs']['total_pct']:.2f}%)**

🎯 **EDGE:**
• TP: {a['tp_pct']:.2f}%
• Custos: {a['costs']['total_pct']:.2f}%
━━━━━━━━━━━━━━━━
• **EDGE LÍQUIDO: {a['edge']['liquido_pct']:.2f}%**
• Mínimo exigido: {a['edge']['min_required']:.2f}%
"""

    if a['violations']:
        msg += f"\n\n🚨 **VIOLAÇÕES ({len(a['violations'])}):**\n"
        for v in a['violations']:
            msg += f"❌ {v}\n"
    
    if a['warnings']:
        msg += f"\n\n⚠️ **AVISOS ({len(a['warnings'])}):**\n"
        for w in a['warnings']:
            msg += f"⚠️ {w}\n"
    
    if not a['violations']:
        msg += "\n\n✅ Trade aprovado (com ressalvas)" if a['warnings'] else "\n\n✅ Trade totalmente aprovado"
    else:
        msg += "\n\n❌ **TRADE NÃO DEVERIA TER SIDO EXECUTADO**"
    
    return msg


def generate_email_report(analysis):
    """Gera relatório completo para Email (HTML)."""
    if not analysis:
        return "<p>Erro ao gerar relatório</p>"
    
    a = analysis
    regime_emoji = "🐂" if a['regime']['btc_regime'] == "BULL" else "🐻" if a['regime']['btc_regime'] == "BEAR" else "⚖️"
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #1a1a2e; color: white; padding: 20px; border-radius: 8px; }}
            .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
            .violation {{ background: #ffebee; border-left: 4px solid #f44336; }}
            .warning {{ background: #fff3e0; border-left: 4px solid #ff9800; }}
            .success {{ background: #e8f5e9; border-left: 4px solid #4caf50; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f5f5f5; font-weight: bold; }}
            .metric {{ font-size: 24px; font-weight: bold; color: #1976d2; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🚨 RELATÓRIO COMPLETO DE TRADE - TIER {a['tier']}</h1>
            <p><strong>{a['symbol']}</strong> | ${a['price']:.4f} | {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
        </div>
        
        <div class="section">
            <h2>📊 1. DADOS DE MERCADO (24H)</h2>
            <table>
                <tr><th>Métrica</th><th>Valor</th><th>Limite Sandra 2.1</th><th>Status</th></tr>
                <tr>
                    <td>Variação 24h</td>
                    <td>{a['market_data']['var_24h']:+.2f}%</td>
                    <td>> -10%</td>
                    <td>{"✅" if a['market_data']['var_24h'] > -10 else "❌"}</td>
                </tr>
                <tr>
                    <td>Volume 24h</td>
                    <td>${a['market_data']['volume_24h']:,.0f}</td>
                    <td>> ${a['limits']['min_volume']:,}</td>
                    <td>{"✅" if a['market_data']['volume_24h'] >= a['limits']['min_volume'] else "⚠️"}</td>
                </tr>
                <tr>
                    <td>Spread</td>
                    <td>{a['market_data']['spread_bps']:.1f} bps</td>
                    <td>< {a['limits']['max_spread']} bps</td>
                    <td>{"✅" if a['market_data']['spread_bps'] <= a['limits']['max_spread'] else "⚠️"}</td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <h2>🌊 2. REGIME BTC (1h)</h2>
            <p><strong>Status:</strong> {regime_emoji} <span class="metric">{a['regime']['btc_regime']}</span></p>
            <table>
                <tr><th>Indicador</th><th>Valor</th></tr>
                <tr><td>EMA 50</td><td>${a['regime']['ema50']:,.2f}</td></tr>
                <tr><td>EMA 200</td><td>${a['regime']['ema200']:,.2f}</td></tr>
            </table>
            <p><strong>Interpretação:</strong> {"EMA50 > EMA200 = Mercado em alta" if a['regime']['btc_regime'] == "BULL" else "EMA50 < EMA200 = Mercado em baixa" if a['regime']['btc_regime'] == "BEAR" else "Mercado lateral"}</p>
            <p><strong>Regra TIER B:</strong> {"✅ Atendida (regime BULL permite)" if a['regime']['btc_regime'] == "BULL" else "❌ VIOLADA (TIER B exige BULL)"}</p>
        </div>
        
        <div class="section">
            <h2>💰 3. ANÁLISE DE CUSTOS E EDGE</h2>
            <table>
                <tr><th>Item</th><th>USD</th><th>%</th></tr>
                <tr><td>Taxa de compra</td><td>${a['costs']['fee_buy']:.3f}</td><td>0.10%</td></tr>
                <tr><td>Taxa de venda (est)</td><td>${a['costs']['fee_sell']:.3f}</td><td>0.10%</td></tr>
                <tr><td>Spread do orderbook</td><td>${a['costs']['spread']:.3f}</td><td>{a['market_data']['spread_pct']:.3f}%</td></tr>
                <tr><td>Slippage estimado</td><td>${a['costs']['slippage']:.3f}</td><td>0.15%</td></tr>
                <tr style="border-top: 2px solid #333; font-weight: bold;">
                    <td>CUSTO TOTAL</td>
                    <td>${a['costs']['total_usd']:.3f}</td>
                    <td>{a['costs']['total_pct']:.2f}%</td>
                </tr>
            </table>
            
            <h3>🎯 Cálculo de EDGE:</h3>
            <table>
                <tr><th>Métrica</th><th>Valor</th></tr>
                <tr><td>Take Profit proposto</td><td class="metric">+{a['tp_pct']:.2f}%</td></tr>
                <tr><td>Custo total</td><td>-{a['costs']['total_pct']:.2f}%</td></tr>
                <tr style="border-top: 2px solid #333; font-weight: bold;">
                    <td>EDGE LÍQUIDO</td>
                    <td class="metric" style="color: {'green' if a['edge']['liquido_pct'] >= a['edge']['min_required'] else 'red'}">
                        {a['edge']['liquido_pct']:+.2f}%
                    </td>
                </tr>
                <tr>
                    <td>Edge mínimo TIER {a['tier']}</td>
                    <td>{a['edge']['min_required']:.2f}%</td>
                </tr>
            </table>
            
            <p><strong>Interpretação:</strong> {"✅ Edge suficiente" if a['edge']['liquido_pct'] >= a['edge']['min_required'] else "⚠️ Edge INSUFICIENTE - margem muito apertada!"}</p>
        </div>
        
        <div class="section">
            <h2>🎯 4. GESTÃO DE RISCO</h2>
            <table>
                <tr><th>Parâmetro</th><th>Valor</th></tr>
                <tr><td>Posição</td><td>${a['position_size']:.2f}</td></tr>
                <tr><td>Stop Loss</td><td>{a['sl_pct']:.2f}% (${a['price'] * (1 + a['sl_pct']/100):.4f})</td></tr>
                <tr><td>Take Profit</td><td>+{a['tp_pct']:.2f}% (${a['price'] * (1 + a['tp_pct']/100):.4f})</td></tr>
                <tr><td>Risco:Recompensa</td><td>{abs(a['tp_pct'] / a['sl_pct']):.2f}:1</td></tr>
            </table>
        </div>
"""
    
    if a['violations']:
        html += f"""
        <div class="section violation">
            <h2>🚨 VIOLAÇÕES CRÍTICAS ({len(a['violations'])})</h2>
            <ul>
"""
        for v in a['violations']:
            html += f"<li><strong>❌ {v}</strong></li>"
        html += """
            </ul>
            <p style="color: #d32f2f; font-weight: bold;">⚠️ ESTE TRADE NÃO DEVERIA TER SIDO EXECUTADO SEGUNDO SANDRA 2.1</p>
        </div>
"""
    
    if a['warnings']:
        html += f"""
        <div class="section warning">
            <h2>⚠️ AVISOS ({len(a['warnings'])})</h2>
            <ul>
"""
        for w in a['warnings']:
            html += f"<li>⚠️ {w}</li>"
        html += """
            </ul>
            <p><strong>Observação:</strong> Avisos não impedem o trade, mas aumentam o risco.</p>
        </div>
"""
    
    if not a['violations'] and not a['warnings']:
        html += """
        <div class="section success">
            <h2>✅ TRADE TOTALMENTE APROVADO</h2>
            <p>Todos os critérios Sandra 2.1 foram atendidos.</p>
        </div>
"""
    elif not a['violations']:
        html += """
        <div class="section warning">
            <h2>⚠️ TRADE APROVADO COM RESSALVAS</h2>
            <p>Trade atende critérios mínimos, mas com avisos importantes.</p>
        </div>
"""
    
    html += f"""
        <div class="section">
            <h2>📋 5. CONCLUSÃO E RECOMENDAÇÃO</h2>
            <p><strong>Data/Hora:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</p>
            <p><strong>Símbolo:</strong> {a['symbol']}</p>
            <p><strong>TIER:</strong> {a['tier']} ({'Major' if a['tier'] == 'A' else 'Emergente/DEGEN'})</p>
            
            {"<p style='color: #d32f2f; font-weight: bold;'>❌ DECISÃO: Este trade VIOLA as regras Sandra 2.1 e não deveria ter sido executado.</p>" if a['violations'] else ""}
            {"<p style='color: #ff6f00; font-weight: bold;'>⚠️ DECISÃO: Trade aprovado, mas com margem de erro pequena. Monitorar de perto.</p>" if a['warnings'] and not a['violations'] else ""}
            {"<p style='color: #2e7d32; font-weight: bold;'>✅ DECISÃO: Trade totalmente aprovado segundo Sandra 2.1.</p>" if not a['violations'] and not a['warnings'] else ""}
            
            <p><strong>Próximos passos:</strong></p>
            <ul>
                <li>Monitorar Stop Loss: {a['sl_pct']:.2f}%</li>
                <li>Alvo Take Profit: {a['tp_pct']:.2f}%</li>
                <li>Atenção especial aos avisos acima</li>
            </ul>
        </div>
        
        <hr>
        <p style="color: #666; font-size: 12px;">
            <strong>Sistema:</strong> SANDRA 2.1 - Trading Bot Institucional<br>
            <strong>Fontes:</strong> Binance API (tempo real), pandas_ta, Fear & Greed Index<br>
            <strong>Documentação:</strong> docs/SANDRA_2.1_SYSTEM_PROMPT.md
        </p>
    </body>
    </html>
    """
    
    return html


def send_email_report(analysis, to_email=None):
    """Envia relatório por email."""
    try:
        if not os.getenv('EMAIL_ENABLED', 'false').lower() == 'true':
            print("⚠️ Email desabilitado no .env")
            return False
        
        to_email = to_email or os.getenv('EMAIL_TO')
        if not to_email:
            print("⚠️ EMAIL_TO não configurado")
            return False
        
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        
        if not all([smtp_host, smtp_user, smtp_pass]):
            print("⚠️ Configurações SMTP incompletas")
            return False
        
        # Criar mensagem
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚨 RELATÓRIO TRADE - {analysis['symbol']} (TIER {analysis['tier']})"
        msg['From'] = smtp_user
        msg['To'] = to_email
        
        # Corpo HTML
        html_content = generate_email_report(analysis)
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Enviar
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f"✅ Email enviado para {to_email}")
        return True
    
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False


def send_complete_report(exchange, symbol, position_size, tp_pct, sl_pct, tier='B', send_telegram_func=None):
    """
    Envia relatório completo via Email + Telegram.
    
    Args:
        exchange: instância ccxt
        symbol: par (ex: 'STRK/USDT')
        position_size: tamanho em USD
        tp_pct: take profit %
        sl_pct: stop loss %
        tier: 'A' ou 'B'
        send_telegram_func: função para enviar Telegram
    """
    print(f"📊 Gerando relatório completo para {symbol} (TIER {tier})...")
    
    # Análise completa
    analysis = analyze_trade_complete(exchange, symbol, position_size, tp_pct, sl_pct, tier)
    
    if not analysis:
        print("❌ Erro na análise")
        return False
    
    # Email
    email_sent = send_email_report(analysis)
    
    # Telegram
    telegram_sent = False
    if send_telegram_func:
        try:
            telegram_msg = generate_telegram_report(analysis)
            send_telegram_func(telegram_msg)
            telegram_sent = True
            print("✅ Telegram enviado")
        except Exception as e:
            print(f"❌ Erro ao enviar Telegram: {e}")
    
    return {
        'analysis': analysis,
        'email_sent': email_sent,
        'telegram_sent': telegram_sent
    }
