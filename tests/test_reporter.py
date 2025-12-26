#!/usr/bin/env python3
"""
Teste do Sistema de Relatórios (Sandra 2.1)

Simula uma compra TIER B e gera relatório completo.
"""

import sys
import os
from dotenv import load_dotenv

# Importa módulos do sistema
sys.path.insert(0, '/home/ubuntu/projetobinace')
load_dotenv('/home/ubuntu/projetobinace/.env')

import trade_reporter
import ccxt

def test_reporter_dry_run():
    """Teste com dados reais da Binance (leitura apenas)."""
    print("🧪 TESTE DO SISTEMA DE RELATÓRIOS (Sandra 2.1)")
    print("=" * 60)
    
    # Configura Binance (leitura pública, sem necessidade de API key)
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    
    # Símbolos de teste
    test_cases = [
        {'symbol': 'BTC/USDT', 'tier': 'A', 'position_size': 100, 'tp': 3.0, 'sl': 1.5},
        {'symbol': 'STRK/USDT', 'tier': 'B', 'position_size': 11, 'tp': 2.7, 'sl': 1.2},
        {'symbol': 'DOGE/USDT', 'tier': 'B', 'position_size': 15, 'tp': 5.0, 'sl': 2.0},
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*60}")
        print(f"TESTE {i}/3: {test['symbol']} (TIER {test['tier']})")
        print(f"{'='*60}")
        
        try:
            # Análise completa
            analysis = trade_reporter.analyze_trade_complete(
                exchange=exchange,
                symbol=test['symbol'],
                position_size=test['position_size'],
                tp_pct=test['tp'],
                sl_pct=test['sl'],
                tier=test['tier']
            )
            
            if not analysis:
                print("❌ Erro na análise")
                continue
            
            # Mostra resumo
            print(f"\n📊 RESUMO DA ANÁLISE:")
            print(f"  • Preço: ${analysis['price']:.4f}")
            print(f"  • Variação 24h: {analysis['market_data']['var_24h']:+.2f}%")
            print(f"  • Volume 24h: ${analysis['market_data']['volume_24h']:,.0f}")
            print(f"  • Spread: {analysis['market_data']['spread_bps']:.1f} bps")
            
            regime = analysis['regime']
            regime_emoji = "🐂" if regime['btc_regime'] == "BULL" else "🐻" if regime['btc_regime'] == "BEAR" else "⚖️"
            print(f"\n🌊 REGIME BTC:")
            print(f"  • Status: {regime_emoji} {regime['btc_regime']}")
            print(f"  • EMA50: ${regime['ema50']:,.2f}")
            print(f"  • EMA200: ${regime['ema200']:,.2f}")
            
            print(f"\n💰 CUSTOS E EDGE:")
            print(f"  • Custos totais: ${analysis['costs']['total_usd']:.3f} ({analysis['costs']['total_pct']:.2f}%)")
            print(f"  • Take Profit: {analysis['tp_pct']:.2f}%")
            print(f"  • Edge líquido: {analysis['edge']['liquido_pct']:.2f}%")
            print(f"  • Edge mínimo: {analysis['edge']['min_required']:.2f}%")
            
            edge_status = "✅" if analysis['edge']['liquido_pct'] >= analysis['edge']['min_required'] else "⚠️"
            print(f"  • Status: {edge_status}")
            
            if analysis['violations']:
                print(f"\n🚨 VIOLAÇÕES ({len(analysis['violations'])}):")
                for v in analysis['violations']:
                    print(f"  ❌ {v}")
            
            if analysis['warnings']:
                print(f"\n⚠️ AVISOS ({len(analysis['warnings'])}):")
                for w in analysis['warnings']:
                    print(f"  ⚠️ {w}")
            
            if not analysis['violations'] and not analysis['warnings']:
                print(f"\n✅ Trade totalmente aprovado!")
            elif not analysis['violations']:
                print(f"\n⚠️ Trade aprovado com ressalvas")
            else:
                print(f"\n❌ Trade NÃO deveria ser executado")
            
            # Simula envio de relatório (apenas TIER B)
            if test['tier'] == 'B':
                print(f"\n📧 SIMULANDO ENVIO DE RELATÓRIO...")
                
                # Gera relatórios (sem enviar de verdade)
                email_html = trade_reporter.generate_email_report(analysis)
                telegram_msg = trade_reporter.generate_telegram_report(analysis)
                
                print(f"  ✅ Email HTML gerado: {len(email_html)} caracteres")
                print(f"  ✅ Telegram gerado: {len(telegram_msg)} caracteres")
                
                # Verifica configuração de email
                email_enabled = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
                email_to = os.getenv('EMAIL_TO', '')
                
                if email_enabled and email_to:
                    print(f"  📧 Email seria enviado para: {email_to}")
                else:
                    print(f"  ⚠️ Email desabilitado ou não configurado")
            else:
                print(f"\n📊 TIER A não gera relatório automático")
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"✅ TESTE CONCLUÍDO")
    print(f"{'='*60}")

if __name__ == '__main__':
    test_reporter_dry_run()
