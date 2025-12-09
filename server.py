import os
import json
import time
import random
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import ccxt
import pandas as pd
import numpy as np
import requests
import asyncio
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configurações
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not API_KEY or API_KEY == 'sua_api_key_aqui':
    print("\n" + "="*50)
    print("❌ AVISO: CHAVES DE API NÃO ENCONTRADAS")
    print("👉 Edite o arquivo .env e coloque suas chaves da Binance")
    print("="*50 + "\n")

SYMBOL = os.getenv('SYMBOL', 'BTC/USDT')
AMOUNT_INVEST = float(os.getenv('AMOUNT_INVEST', 11.0))
FEE_RATE = 0.001  # 0.1%

# Configuração OpenAI
openai_client = None
if OPENAI_API_KEY and OPENAI_API_KEY != 'your_openai_api_key_here':
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("🧠 OpenAI (GPT) Configurado")
    except Exception as e:
        print(f"⚠️ Erro ao configurar OpenAI: {e}")

# Estado Global
lab_state = {
    'strategies': {
        'aggressive': {'name': 'Trading Real 💰', 'balance': 0.0, 'trades': [], 'position': None}
    },
    'selected_strategy': 'aggressive',  # Única estratégia - Trading Real
    'is_live': True,  # MODO REAL SEMPRE ATIVADO
    'running': True,  # Controle Mestre (ON/OFF) - Inicia LIGADO
    'real_balance': 0.0,
    'last_update': '',
    'current_price': 0.0,
    'current_symbol': '---', # Símbolo atual sendo analisado
    'status': 'Parado', # Status inicial
    'market_overview': {}, # Radar de Mercado (Todas as moedas)
    'indicators': { # Novos indicadores para o frontend
        'rsi': 0.0,
        'bb_lower': 0.0,
        'bb_upper': 0.0
    },
    'diagnostics': {},  # Diagnóstico por moeda (motivo de não comprar)
    'user_info': {
        'uid': '---',
        'type': '---',
        'can_trade': False,
        'balances': {},
        'total_brl': 0.0,
        'usdt_brl_rate': 0.0
    },
    'last_trade_time': 0  # Cooldown para evitar trades em loop
}

# Exchange
exchange = None
try:
    # Primeiro, obtém a diferença de tempo com o servidor da Binance
    exchange_temp = ccxt.binance({'enableRateLimit': True})
    try:
        server_time = exchange_temp.fetch_time()
        local_time = int(time.time() * 1000)
        time_diff = server_time - local_time
        print(f"⏰ Sincronizando tempo: diferença de {time_diff}ms com servidor Binance")
    except:
        time_diff = 0
    
    exchange_config = {
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'spot',
            'adjustForTimeDifference': True,
            'recvWindow': 60000,  # 60 segundos de tolerância
            'timeDifference': time_diff  # Aplica correção de tempo
        }
    }
    
    # Configuração de Proxy (se existir)
    proxy_url = os.getenv('PROXY_URL')
    if proxy_url:
        exchange_config['proxies'] = {
            'http': proxy_url,
            'https': proxy_url
        }
        print(f"🌍 Usando Proxy configurado: {proxy_url}")

    exchange = ccxt.binance(exchange_config)
    
    # Força sincronização de tempo
    print("⏳ Sincronizando relógio com a Binance...")
    diff = exchange.load_time_difference()
    print(f"✅ Relógio sincronizado. Diferença: {diff}ms")
    
    print("✅ Exchange conectada")
except Exception as e:
    print(f"⚠️ Erro ao conectar Exchange: {e}")


def load_lab_data():
    """Carrega dados persistidos do laboratório."""
    try:
        with open('lab_data.json', 'r') as f:
            data = json.load(f)
            lab_state['strategies'] = data.get(
                'strategies', lab_state['strategies'])
            lab_state['selected_strategy'] = data.get(
                'selected_strategy', 'conservative')
            lab_state['is_live'] = data.get('is_live', False)
            lab_state['running'] = data.get('running', False)
            print("📂 Dados do laboratório carregados")
    except FileNotFoundError:
        print("📝 Criando novo laboratório")
        save_lab_data()


def save_lab_data():
    """Salva estado atual do laboratório."""
    data = {
        'strategies': lab_state['strategies'],
        'selected_strategy': lab_state['selected_strategy'],
        'is_live': lab_state['is_live'],
        'running': lab_state['running'],
        'last_save': datetime.now().isoformat()
    }
    with open('lab_data.json', 'w') as f:
        json.dump(data, f, indent=2)


def calculate_rsi(prices, period=14):
    """Calcula RSI."""
    if len(prices) < period:
        return 50

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger(prices, period=20):
    """Calcula Bandas de Bollinger."""
    if len(prices) < period:
        return prices[-1], prices[-1], prices[-1]

    sma = np.mean(prices[-period:])
    std = np.std(prices[-period:])

    upper = sma + (2 * std)
    lower = sma - (2 * std)

    return upper, sma, lower


# --- INTEGRAÇÃO TELEGRAM & GPT ---

def send_telegram_message(message):
    """Envia mensagem para o Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_TOKEN == 'your_telegram_token_here':
        print("⚠️ Telegram não configurado. Mensagem não enviada.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("📨 Mensagem Telegram enviada com sucesso!")
        else:
            print(f"❌ Erro Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Erro ao enviar Telegram: {e}")

def analyze_market_with_gpt(symbol, price, rsi, bb_lower, action_type):
    """Usa GPT para analisar o contexto do trade."""
    if not openai_client:
        return "🤖 IA não configurada."

    prompt = f"""
    Você é um analista de trading sênior.
    Ação: {action_type} em {symbol}
    Preço Atual: {price}
    RSI (14): {rsi:.2f}
    Bandas de Bollinger (Lower): {bb_lower:.2f}
    
    Analise brevemente (máximo 2 frases) se esta operação faz sentido técnico com base no RSI e Bollinger.
    Seja direto e use emojis.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um assistente de trading cripto conciso."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Erro GPT: {e}")
        return "🤖 Erro na análise de IA."

# ---------------------------------


# Lista de moedas para monitorar (ordenadas por preço aproximado - mais baratas primeiro)
WATCHLIST = [
    'XRP/USDT',    # ~$2
    'ADA/USDT',    # ~$1
    'DOGE/USDT',   # ~$0.40
    'DOT/USDT',    # ~$8
    'LINK/USDT',   # ~$25
    'LTC/USDT',    # ~$100
    'SOL/USDT',    # ~$200
    'BNB/USDT',    # ~$700
    'ETH/USDT',    # ~$4000
    'BTC/USDT',    # ~$90000
]

# Valor mínimo de ordem na Binance (em USDT)
MIN_ORDER_VALUE = 11.0

def fetch_market_data(symbol):
    """Busca dados de mercado para análise."""
    try:
        if not exchange:
            return None, None, None, None

        # Busca últimas 100 velas de 5 minutos
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=100)
        closes = [candle[4] for candle in ohlcv]
        current_price = closes[-1]

        rsi = calculate_rsi(closes)
        upper, sma, lower = calculate_bollinger(closes)

        return current_price, rsi, lower, upper
    except Exception as e:
        print(f"❌ Erro ao buscar dados ({symbol}): {e}")
        return None, None, None, None


def check_strategy_signal(strategy_name, price, rsi, bb_lower):
    """Verifica se dá sinal de compra (Trading Real)."""
    # Tolerância: permite comprar até 1% acima da banda inferior (mais flexível)
    tolerance = bb_lower * 0.01  # 1% de tolerância
    
    # RSI < 35 (mais oversold = mais seguro) e preço próximo da banda inferior
    # Ou RSI < 30 (extremamente oversold) independente do preço
    rsi_oversold = rsi < 35
    rsi_extreme = rsi < 30
    price_good = price <= bb_lower + tolerance
    
    return (rsi_oversold and price_good) or rsi_extreme


def get_diagnostic(strategy_name, price, rsi, bb_lower, position=None):
    """Gera diagnóstico legível explicando por que não está comprando/vendendo."""
    
    # Se tem posição aberta, calcula lucro
    if position:
        entry_price = position.get('entry_price', price)
        profit_pct = ((price - entry_price) / entry_price) * 100
        emoji = "📈" if profit_pct > 0 else "📉"
        return f"{emoji} COMPRADO (Lucro: {profit_pct:+.2f}%)"
    
    # Verifica saldo primeiro
    usdt_balance = lab_state.get('real_balance', 0.0)
    if usdt_balance < MIN_ORDER_VALUE:
        return f"💸 SALDO BAIXO (${usdt_balance:.2f} < ${MIN_ORDER_VALUE})"
    
    # Analisa condições de compra (novos parâmetros)
    issues = []
    rsi_target = 35  # Mais conservador
    rsi_extreme = 30  # Compra forte
    tolerance = bb_lower * 0.01  # 1% tolerância
    
    # Se RSI extremamente baixo, é sinal forte
    if rsi < rsi_extreme:
        return "🚨 RSI EXTREMO! OPORTUNIDADE DE COMPRA!"
    
    if rsi >= rsi_target:
        issues.append(f"RSI Alto ({rsi:.1f} / Alvo: <{rsi_target})")
    if price > bb_lower + tolerance:
        diff_pct = ((price - bb_lower) / bb_lower) * 100
        issues.append(f"Preço {diff_pct:.1f}% acima da banda")
    
    if not issues:
        return "🎯 PRONTO PARA COMPRAR!"
    
    return "⏳ " + " | ".join(issues)


def check_exit_signal(entry_price, current_price, rsi, bb_upper=None):
    """Verifica sinal de saída - COMPENSANDO TAXAS (0.2% total)."""
    profit_pct = ((current_price - entry_price) / entry_price) * 100
    
    # Tolerância para banda superior (vende até 1% abaixo)
    price_at_upper = False
    if bb_upper:
        tolerance = bb_upper * 0.01  # 1% de tolerância
        price_at_upper = current_price >= bb_upper - tolerance

    # === LÓGICA COM TAXAS COMPENSADAS ===
    # Taxa Binance: 0.1% compra + 0.1% venda = 0.2% total
    # 
    # TAKE PROFIT (lucro líquido real):
    # - 2.0% bruto = 1.8% líquido ✅
    # - 1.5% bruto = 1.3% líquido ✅
    # - 1.2% bruto = 1.0% líquido ✅
    #
    # STOP LOSS:
    # - 2.5% perda bruta = 2.7% perda real (com taxas)
    
    should_sell = False
    reason = []
    
    # Take Profits (JÁ COMPENSANDO TAXAS)
    if profit_pct >= 2.0:  # Lucro líquido: 1.8%
        should_sell = True
        reason.append(f"🎯 LUCRO {profit_pct:.1f}% (líquido ~{profit_pct-0.2:.1f}%)")
    elif profit_pct >= 1.5 and rsi > 55:  # Lucro líquido: 1.3%
        should_sell = True
        reason.append(f"📈 Lucro {profit_pct:.1f}% + RSI bom ({rsi:.0f})")
    elif profit_pct >= 1.2 and rsi > 60:  # Lucro líquido: 1.0%
        should_sell = True
        reason.append(f"💰 Lucro {profit_pct:.1f}% + Momentum ({rsi:.0f})")
    elif price_at_upper and profit_pct > 0.5:  # Lucro líquido: 0.3%
        should_sell = True
        reason.append(f"📊 Banda Superior + Lucro {profit_pct:.1f}%")
    
    # Stop Loss (proteção - melhor perder pouco que muito)
    if profit_pct <= -2.0:
        should_sell = True
        reason.append(f"🛑 Stop Loss {profit_pct:.1f}%")
    
    # RSI sobrecomprado com lucro
    if rsi > 70 and profit_pct > 0.5:
        should_sell = True
        reason.append(f"🔥 RSI Alto ({rsi:.0f}) + Lucro {profit_pct:.1f}%")
    
    if should_sell:
        print(f"🔔 SINAL DE VENDA: {', '.join(reason)}")
    
    return should_sell


def convert_brl_to_usdt():
    """Converte BRL para USDT automaticamente quando necessário."""
    try:
        balance = exchange.fetch_balance()
        brl_balance = balance['total'].get('BRL', 0.0)
        usdt_balance = balance['total'].get('USDT', 0.0)
        
        # Se já tem USDT suficiente, não precisa converter
        if usdt_balance >= MIN_ORDER_VALUE:
            return usdt_balance
        
        # Se não tem BRL suficiente para converter
        if brl_balance < 50:  # Mínimo para conversão (BRL)
            print(f"⚠️ Saldo BRL insuficiente para conversão: R${brl_balance:.2f}")
            return usdt_balance
        
        # Busca cotação BRL/USDT
        try:
            ticker = exchange.fetch_ticker('USDT/BRL')
            usdt_price_brl = ticker['last']  # Preço de 1 USDT em BRL
            
            # Calcula quantidade de USDT a comprar (usando 95% do BRL para taxas)
            brl_to_use = brl_balance * 0.95
            usdt_qty = brl_to_use / usdt_price_brl
            
            print(f"🔄 Convertendo R${brl_to_use:.2f} para ~${usdt_qty:.2f} USDT...")
            
            # Executa ordem de compra de USDT com BRL
            order = exchange.create_market_buy_order('USDT/BRL', usdt_qty)
            
            new_usdt = order['filled']
            print(f"✅ Conversão concluída! Recebido: ${new_usdt:.2f} USDT")
            
            # Atualiza saldo no estado
            lab_state['real_balance'] = new_usdt
            
            return new_usdt
            
        except Exception as e:
            print(f"❌ Erro na conversão BRL->USDT: {e}")
            # Tenta par inverso BRL/USDT
            try:
                ticker = exchange.fetch_ticker('BRL/USDT')
                # Vende BRL para obter USDT
                order = exchange.create_market_sell_order('BRL/USDT', brl_balance * 0.95)
                new_usdt = order['cost']  # USDT recebido
                print(f"✅ Conversão alternativa concluída! Recebido: ${new_usdt:.2f} USDT")
                lab_state['real_balance'] = new_usdt
                return new_usdt
            except:
                return usdt_balance
            
    except Exception as e:
        print(f"❌ Erro ao verificar saldos para conversão: {e}")
        return 0.0


def execute_real_trade(action, price, symbol):
    """Executa trade REAL na Binance."""
    if not exchange or not API_KEY or not SECRET:
        print("⚠️ Modo real desabilitado: sem chaves API")
        return False
    
    # COOLDOWN: Espera 60 segundos entre trades para evitar loop
    TRADE_COOLDOWN = 60  # segundos
    current_time = time.time()
    last_trade = lab_state.get('last_trade_time', 0)
    
    if current_time - last_trade < TRADE_COOLDOWN:
        remaining = int(TRADE_COOLDOWN - (current_time - last_trade))
        print(f"⏳ Cooldown ativo: aguarde {remaining}s antes do próximo trade")
        return False

    try:
        strategy_key = lab_state['selected_strategy']
        strategy = lab_state['strategies'][strategy_key]

        if action == 'buy':
            # VERIFICAÇÃO DE SALDO ANTES DE COMPRAR
            usdt_balance = lab_state.get('real_balance', 0.0)
            
            # Se não tem USDT suficiente, tenta converter BRL para USDT
            if usdt_balance < MIN_ORDER_VALUE:
                print(f"⚠️ Saldo USDT baixo (${usdt_balance:.2f}). Tentando converter BRL...")
                usdt_balance = convert_brl_to_usdt()
                
                # Se ainda não tem saldo após conversão - apenas loga, não envia Telegram repetido
                if usdt_balance < MIN_ORDER_VALUE:
                    print(f"⚠️ Saldo insuficiente: ${usdt_balance:.2f} < ${MIN_ORDER_VALUE}")
                    return False
            
            # Usa o valor disponível (máximo de AMOUNT_INVEST ou saldo disponível)
            invest_amount = min(AMOUNT_INVEST, usdt_balance * 0.95)  # 95% para taxa
            
            if invest_amount < MIN_ORDER_VALUE:
                print(f"⚠️ Valor de investimento muito baixo: ${invest_amount:.2f}")
                return False
            
            qty = invest_amount / price
            
            # Ordem de compra REAL
            order = exchange.create_market_buy_order(symbol, qty)

            trade = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'type': f'BUY REAL ({symbol})',
                'price': order['average'] or price,
                'qty': order['filled'],
                'order_id': order['id'],
                'mode': 'REAL'
            }
            strategy['trades'].append(trade)
            # Salva o símbolo na posição para saber o que vender depois
            strategy['position'] = {
                'entry_price': price, 'qty': order['filled'], 'entry_time': datetime.now().isoformat(), 'symbol': symbol}
            
            print(
                f"💰 [{strategy['name']}] COMPRA REAL: {order['filled']} {symbol} @ ${order['average']:.2f}")
            
            # Notificação Telegram (sem IA para economizar tokens)
            rsi = lab_state['indicators']['rsi']
            msg = f"💰 *COMPRA REAL*\\n\\n🪙 Moeda: {symbol}\\n💵 Preço: ${price:.2f}\\n📊 RSI: {rsi:.1f}"
            send_telegram_message(msg)
            
            # Atualiza cooldown
            lab_state['last_trade_time'] = time.time()
            
            return True

        elif action == 'sell':
            # Busca posição aberta para saber quanto vender
            if strategy['position']:
                qty = strategy['position']['qty']
                entry_price_original = strategy['position']['entry_price']
                
                # Verifica se realmente temos a moeda na carteira antes de vender
                try:
                    balance = exchange.fetch_balance()
                    coin = symbol.split('/')[0]  # Ex: 'XRP' de 'XRP/USDT'
                    coin_balance = balance['free'].get(coin, 0)
                    
                    if coin_balance <= 0:
                        print(f"⚠️ Nenhum saldo de {coin} na carteira!")
                        strategy['position'] = None
                        send_telegram_message(f"⚠️ *POSIÇÃO LIMPA*\\n\\nNão há {coin} na carteira para vender.")
                        return False
                    
                    # Se o saldo real é menor que o registrado, vende o que tem
                    if coin_balance < qty:
                        print(f"⚠️ Saldo real de {coin} menor que registrado: {coin_balance:.8f} < {qty:.8f}")
                        print(f"📤 Vendendo o saldo disponível: {coin_balance:.8f} {coin}")
                        qty = coin_balance
                    
                except Exception as e:
                    print(f"⚠️ Erro ao verificar saldo: {e}")
                
                order = exchange.create_market_sell_order(symbol, qty)

                trade = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'type': f'SELL REAL ({symbol})',
                    'price': order['average'] or price,
                    'qty': order['filled'],
                    'order_id': order['id'],
                    'mode': 'REAL'
                }
                strategy['trades'].append(trade)
                strategy['position'] = None # Limpa posição
                print(
                    f"💵 [{strategy['name']}] VENDA REAL: {order['filled']} {symbol} @ ${order['average']:.2f}")
                
                # Notificação Telegram (sem IA para economizar tokens)
                entry_price = strategy['position']['entry_price'] if strategy.get('position') else price
                profit_pct = ((price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                rsi = lab_state['indicators']['rsi']
                msg = f"💵 *VENDA REAL*\\n\\n🪙 Moeda: {symbol}\\n💵 Preço: ${price:.2f}\\n📈 Lucro: {profit_pct:+.1f}%\\n📊 RSI: {rsi:.1f}"
                send_telegram_message(msg)
                
                # Atualiza cooldown
                lab_state['last_trade_time'] = time.time()
                
                return True

    except Exception as e:
        print(f"❌ ERRO ORDEM REAL: {e}")
        send_telegram_message(f"❌ *ERRO CRÍTICO NA EXECUÇÃO*\\n\\n{str(e)}")
        return False


def detect_existing_positions():
    """Detecta moedas já existentes na carteira e restaura posições."""
    if not exchange:
        return
    
    try:
        balance = exchange.fetch_balance()
        selected = lab_state['selected_strategy']
        strategy = lab_state['strategies'][selected]
        
        # Se já tem posição registrada, não faz nada
        if strategy['position'] is not None:
            return
        
        # Procura por moedas na carteira que estão na WATCHLIST
        for symbol in WATCHLIST:
            coin = symbol.replace('/USDT', '')
            coin_balance = balance['total'].get(coin, 0.0)
            
            if coin_balance > 0:
                # Busca o preço atual
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                coin_value_usdt = coin_balance * current_price
                
                print(f"💰 Encontrado {coin}: {coin_balance:.8f} (${coin_value_usdt:.2f})")
                
                # Se tiver mais de $1 em valor, considera como posição aberta
                if coin_value_usdt >= 1:
                    # Estima o preço de entrada (usa o preço atual como fallback)
                    # Idealmente pegaria do histórico de trades
                    try:
                        trades = exchange.fetch_my_trades(symbol, limit=5)
                        if trades:
                            # Pega o último trade de compra
                            buy_trades = [t for t in trades if t['side'] == 'buy']
                            if buy_trades:
                                entry_price = buy_trades[-1]['price']
                            else:
                                entry_price = current_price
                        else:
                            entry_price = current_price
                    except:
                        entry_price = current_price
                    
                    strategy['position'] = {
                        'entry_price': entry_price,
                        'qty': coin_balance,
                        'entry_time': datetime.now().isoformat(),
                        'symbol': symbol
                    }
                    
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    print(f"🔄 POSIÇÃO RESTAURADA: {coin_balance:.6f} {symbol} @ ${entry_price:.2f} (Lucro: {profit_pct:+.2f}%)")
                    # Não envia Telegram aqui para não spammar
                    return  # Só pode ter uma posição por vez
                    
    except Exception as e:
        print(f"⚠️ Erro ao detectar posições: {e}")


def trading_loop():
    """Loop principal do sistema."""
    print("🚀 Loop de trading iniciado")
    load_lab_data()
    
    # Detecta posições existentes na carteira ao iniciar
    if lab_state['is_live'] and exchange:
        print("🔍 Verificando posições existentes na carteira...")
        detect_existing_positions()

    while True:
        try:
            # Define quais moedas vamos olhar nesta rodada
            # Se já tivermos uma posição aberta, focamos SÓ nela
            active_symbol = None
            
            # Verifica se tem posição real aberta
            if lab_state['is_live']:
                selected = lab_state['selected_strategy']
                if lab_state['strategies'][selected]['position']:
                    active_symbol = lab_state['strategies'][selected]['position'].get('symbol', SYMBOL)
            
            # Verifica outras posições
            if not active_symbol:
                 for s_key in lab_state['strategies']:
                     if lab_state['strategies'][s_key]['position']:
                         active_symbol = lab_state['strategies'][s_key]['position'].get('symbol', SYMBOL)
                         break
            
            target_coins = [active_symbol] if active_symbol else WATCHLIST

            for current_symbol in target_coins:
                # 1. Busca dados de mercado (agora inclui banda superior)
                price, rsi, bb_lower, bb_upper = fetch_market_data(current_symbol)

                if price is not None:
                    lab_state['current_price'] = price
                    lab_state['current_symbol'] = current_symbol # Atualiza o símbolo na interface
                    lab_state['last_update'] = datetime.now().strftime('%H:%M:%S')
                    # Hack para mostrar qual moeda está sendo analisada no frontend (usando status)
                    # lab_state['status'] = f'Analisando {current_symbol}...' 
                    
                    # Atualiza indicadores globais
                    lab_state['indicators']['rsi'] = rsi
                    lab_state['indicators']['bb_lower'] = bb_lower
                    lab_state['indicators']['bb_upper'] = bb_upper
                    
                    # Atualiza Radar de Mercado + Diagnóstico
                    selected_strategy = lab_state['selected_strategy']
                    strategy_position = lab_state['strategies'][selected_strategy]['position']
                    diagnostic = get_diagnostic(selected_strategy, price, rsi, bb_lower, strategy_position)
                    
                    lab_state['market_overview'][current_symbol] = {
                        'price': price,
                        'rsi': rsi,
                        'bb_lower': bb_lower,
                        'bb_upper': bb_upper,
                        'diagnostic': diagnostic,
                        'last_update': datetime.now().strftime('%H:%M:%S')
                    }
                    
                    # Atualiza diagnósticos separados por moeda
                    lab_state['diagnostics'][current_symbol] = diagnostic

                # 2. Lógica de Trading (Apenas se estiver RODANDO)
                if lab_state['running']:
                    lab_state['status'] = f'Rodando 🚀 | {current_symbol}'

                    if price is not None:
                        # LOG DE ANÁLISE
                        current_balance = lab_state.get('real_balance', 0.0)
                        print(f"🔎 {current_symbol}: RSI={rsi:.1f} | Preço=${price:.2f} | Saldo=${current_balance:.2f}")

                        # ========== 2.1 MODO REAL PRIMEIRO! ==========
                    if lab_state['is_live']:
                            selected = lab_state['selected_strategy']
                            strategy = lab_state['strategies'][selected]

                            if strategy['position'] is None:
                                # Sem posição - procura oportunidades de COMPRA
                                tolerance = bb_lower * 0.005
                                price_ok = price <= bb_lower + tolerance
                                rsi_ok = rsi < 45
                                signal = check_strategy_signal(selected, price, rsi, bb_lower)
                                
                                # Mostra debug para TODAS moedas com RSI < 45
                                if rsi_ok:
                                    print(f"📊 {current_symbol} | RSI={rsi:.1f}✅ | Preço=${price:.2f} | BB=${bb_lower:.2f} | Limite=${bb_lower + tolerance:.2f} | PrçOK={price_ok} | SINAL={signal}")
                                
                                if signal:
                                    print(f"🎯 SINAL DE COMPRA DETECTADO para {current_symbol}!")
                                    result = execute_real_trade('buy', price, current_symbol)
                                    if result:
                                        break # Sai do loop de moedas após compra bem-sucedida
                            else:
                                # TEM POSIÇÃO - verifica VENDA
                                pos_symbol = strategy['position'].get('symbol', SYMBOL)
                                entry_price = strategy['position']['entry_price']
                                profit_pct = ((price - entry_price) / entry_price) * 100
                                
                                if pos_symbol == current_symbol:
                                    print(f"📍 POSIÇÃO ATIVA: {pos_symbol} | Entrada: ${entry_price:.2f} | Atual: ${price:.2f} | Lucro: {profit_pct:+.2f}%")
                                    
                                    if check_exit_signal(entry_price, price, rsi, bb_upper):
                                        print(f"💰 VENDENDO {pos_symbol}!")
                                        execute_real_trade('sell', price, current_symbol)

                        # Modo real sempre ativo - sem simulações
                else:
                    lab_state['status'] = 'Em Standby (Monitorando...) zzz'
                
                # Pequena pausa entre moedas para não estourar limite da API
                time.sleep(2)

            # 3. Atualiza saldo real e informações da conta (SEMPRE, para o dashboard)
            if exchange and API_KEY:
                try:
                    # Busca informações detalhadas da conta (UID, Permissões)
                    # Nota: private_get_account é específico da Binance
                    account_info = exchange.private_get_account()
                    
                    lab_state['user_info']['uid'] = account_info.get('uid', 'Não informado')
                    lab_state['user_info']['type'] = account_info.get('accountType', 'SPOT')
                    lab_state['user_info']['can_trade'] = account_info.get('canTrade', False)
                    
                    # Se estiver bloqueado, imprime aviso
                    if not lab_state['user_info']['can_trade']:
                         print(f"⚠️ CONTA BLOQUEADA PELA BINANCE. Resposta: {account_info.get('canTrade')}")

                    # Busca saldos
                    balance = exchange.fetch_balance()
                    
                    # Tenta pegar saldo em USDT ou BRL
                    usdt_balance = balance['total'].get('USDT', 0.0)
                    brl_balance = balance['total'].get('BRL', 0.0)
                    
                    # Define o saldo principal baseado no que tiver mais valor
                    lab_state['real_balance'] = usdt_balance if usdt_balance > brl_balance else brl_balance
                    
                    # Filtra saldos > 0 para exibir
                    relevant_balances = {}
                    total_brl = 0.0
                    
                    # Pega cotação USDT/BRL para converter
                    try:
                        usdt_brl_ticker = exchange.fetch_ticker('USDT/BRL')
                        usdt_brl_price = usdt_brl_ticker['last']
                    except:
                        usdt_brl_price = 5.50  # Fallback
                    
                    for asset, amount in balance['total'].items():
                        if amount > 0:
                            relevant_balances[asset] = amount
                            
                            # Calcula valor em BRL
                            if asset == 'BRL':
                                total_brl += amount
                            elif asset == 'USDT':
                                total_brl += amount * usdt_brl_price
                            else:
                                # Tenta buscar preço da moeda em USDT e converter para BRL
                                try:
                                    ticker = exchange.fetch_ticker(f'{asset}/USDT')
                                    asset_usdt_price = ticker['last']
                                    total_brl += amount * asset_usdt_price * usdt_brl_price
                                except:
                                    pass  # Ignora se não conseguir
                    
                    lab_state['user_info']['balances'] = relevant_balances
                    lab_state['user_info']['total_brl'] = total_brl
                    lab_state['user_info']['usdt_brl_rate'] = usdt_brl_price

                except Exception as e:
                    # Em caso de erro (ex: IP bloqueado), mantém os dados anteriores ou mostra erro
                    # print(f"⚠️ Erro ao atualizar conta: {e}") # Comentado para não poluir log se for erro temporário
                    pass

            # 4. Salva estado
            save_lab_data()

            # time.sleep(5)  # Aguarda 5 segundos (Removido pois já tem sleep no loop de moedas)

        except Exception as e:
            print(f"❌ Erro no loop: {e}")
            time.sleep(10)


# Rotas da API
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/charts')
def charts_page():
    """Página de gráficos das moedas."""
    return render_template('charts.html')


@app.route('/performance')
def performance_page():
    """Página de acompanhamento de performance."""
    return render_template('performance.html')


@app.route('/api/performance')
def get_performance():
    """Retorna estatísticas de performance das trades."""
    try:
        selected = lab_state['selected_strategy']
        trades = lab_state['strategies'][selected].get('trades', [])
        
        # Estatísticas básicas
        total_trades = len(trades)
        
        if total_trades == 0:
            return jsonify({
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_profit_pct': 0,
                'total_profit_brl': 0,
                'best_trade_pct': 0,
                'worst_trade_pct': 0,
                'avg_trade_pct': 0,
                'accumulated_profit': [],
                'trades': [],
                'goal_current': 0,
                'goal_target': 100
            })
        
        # Calcula métricas
        winning_trades = []
        losing_trades = []
        accumulated = []
        cumulative = 0
        
        for trade in trades:
            profit = trade.get('profit_pct', 0)
            if profit >= 0:
                winning_trades.append(trade)
            else:
                losing_trades.append(trade)
            
            cumulative += profit
            accumulated.append({
                'time': trade.get('exit_time', trade.get('time', '')),
                'profit': round(cumulative, 2)
            })
        
        profits = [t.get('profit_pct', 0) for t in trades]
        
        total_profit_pct = sum(profits)
        best_trade = max(profits) if profits else 0
        worst_trade = min(profits) if profits else 0
        avg_trade = total_profit_pct / total_trades if total_trades > 0 else 0
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        # Calcula lucro em BRL baseado no patrimônio atual
        try:
            usdt_balance = 0
            if exchange:
                balance = exchange.fetch_balance()
                usdt_balance = balance.get('USDT', {}).get('total', 0) or 0
            
            # Estima lucro em BRL
            usd_brl = 6.0
            total_profit_brl = (usdt_balance * total_profit_pct / 100) * usd_brl
        except:
            total_profit_brl = 0
        
        # Prepara trades para exibição (últimas 50)
        trades_display = []
        for t in trades[-50:]:
            trades_display.append({
                'symbol': t.get('symbol', ''),
                'type': t.get('action', t.get('type', '')),
                'entry_price': t.get('entry_price', 0),
                'exit_price': t.get('exit_price', 0),
                'profit_pct': t.get('profit_pct', 0),
                'entry_time': t.get('entry_time', t.get('time', '')),
                'exit_time': t.get('exit_time', ''),
                'reason': t.get('reason', '')
            })
        
        return jsonify({
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(win_rate, 1),
            'total_profit_pct': round(total_profit_pct, 2),
            'total_profit_brl': round(total_profit_brl, 2),
            'best_trade_pct': round(best_trade, 2),
            'worst_trade_pct': round(worst_trade, 2),
            'avg_trade_pct': round(avg_trade, 2),
            'accumulated_profit': accumulated,
            'trades': trades_display,
            'goal_current': round(total_profit_brl, 2),
            'goal_target': 100
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Retorna estado completo do laboratório."""
    return jsonify(lab_state)


@app.route('/api/position')
def get_position():
    """Retorna informações da posição ativa com lucro em tempo real."""
    try:
        selected = lab_state['selected_strategy']
        position = lab_state['strategies'][selected].get('position')
        
        if not position:
            return jsonify({'has_position': False})
        
        symbol = position.get('symbol', SYMBOL)
        entry_price = position.get('entry_price', 0)
        qty = position.get('qty', 0)
        entry_time = position.get('entry_time', '')
        
        # Busca preço atual
        current_price = lab_state.get('current_price', entry_price)
        
        # Tenta pegar preço atualizado da API
        if exchange:
            try:
                ticker = exchange.fetch_ticker(symbol)
                current_price = ticker['last']
            except:
                pass
        
        # Calcula lucro/prejuízo
        profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        profit_value = (current_price - entry_price) * qty
        
        # Calcula metas (COMPENSANDO TAXAS 0.2%)
        take_profit_price = entry_price * 1.02   # +2% bruto = ~1.8% líquido
        stop_loss_price = entry_price * 0.98     # -2%
        
        # Valor da posição
        position_value = current_price * qty
        entry_value = entry_price * qty
        
        return jsonify({
            'has_position': True,
            'symbol': symbol,
            'entry_price': entry_price,
            'current_price': current_price,
            'qty': qty,
            'entry_time': entry_time,
            'profit_pct': profit_pct,
            'profit_value': profit_value,
            'take_profit_price': take_profit_price,
            'stop_loss_price': stop_loss_price,
            'position_value': position_value,
            'entry_value': entry_value,
            'distance_to_tp': ((take_profit_price - current_price) / current_price) * 100,
            'distance_to_sl': ((current_price - stop_loss_price) / current_price) * 100
        })
        
    except Exception as e:
        return jsonify({'has_position': False, 'error': str(e)})


@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    """Retorna dados de velas e indicadores para gráfico."""
    try:
        # Converte símbolo (BTC-USDT -> BTC/USDT)
        symbol_clean = symbol.replace('-', '/')
        
        if not exchange:
            return jsonify({'error': 'Exchange não conectada'}), 500
        
        # Busca últimas 100 velas de 5 minutos
        ohlcv = exchange.fetch_ohlcv(symbol_clean, '5m', limit=100)
        
        # Formata dados
        candles = []
        closes = []
        for candle in ohlcv:
            candles.append({
                'time': candle[0],  # timestamp
                'open': candle[1],
                'high': candle[2],
                'low': candle[3],
                'close': candle[4],
                'volume': candle[5]
            })
            closes.append(candle[4])
        
        # Calcula indicadores
        rsi = calculate_rsi(closes)
        upper, sma, lower = calculate_bollinger(closes)
        
        # Calcula RSI histórico (últimos 50 pontos)
        rsi_history = []
        for i in range(50, len(closes)):
            rsi_val = calculate_rsi(closes[:i+1])
            rsi_history.append({
                'time': ohlcv[i][0],
                'value': rsi_val
            })
        
        # Calcula Bollinger histórico
        bb_history = []
        for i in range(20, len(closes)):
            u, m, l = calculate_bollinger(closes[:i+1])
            bb_history.append({
                'time': ohlcv[i][0],
                'upper': u,
                'middle': m,
                'lower': l
            })
        
        return jsonify({
            'symbol': symbol_clean,
            'candles': candles[-50:],  # Últimas 50 velas
            'current_price': closes[-1],
            'rsi': {
                'current': rsi,
                'history': rsi_history[-50:]
            },
            'bollinger': {
                'upper': upper,
                'middle': sma,
                'lower': lower,
                'history': bb_history[-50:]
            },
            'last_update': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist')
def get_watchlist():
    """Retorna lista de moedas monitoradas."""
    return jsonify({
        'watchlist': WATCHLIST,
        'market_overview': lab_state.get('market_overview', {})
    })


@app.route('/api/select_strategy', methods=['POST'])
def select_strategy():
    """Seleciona qual estratégia usar no modo real."""
    data = request.json
    strategy_key = data.get('strategy')

    if strategy_key in lab_state['strategies']:
        lab_state['selected_strategy'] = strategy_key
        save_lab_data()
        return jsonify({'success': True, 'selected': strategy_key})

    return jsonify({'success': False, 'error': 'Estratégia inválida'}), 400


@app.route('/api/toggle_live', methods=['POST'])
def toggle_live():
    """Liga/Desliga o modo real."""
    data = request.json
    is_live = data.get('is_live', False)

    if is_live and (not API_KEY or not SECRET):
        return jsonify({'success': False, 'error': 'Chaves API não configuradas'}), 400

    lab_state['is_live'] = is_live
    save_lab_data()

    status_text = "ATIVADO ✅" if is_live else "DESATIVADO 🔴"
    print(f"{'='*60}")
    print(f"🔥 MODO REAL {status_text}")
    print(f"{'='*60}")

    return jsonify({'success': True, 'is_live': is_live})


@app.route('/api/toggle_running', methods=['POST'])
def toggle_running():
    """Liga/Desliga o robô (Master Switch)."""
    data = request.json
    running = data.get('running', False)
    
    lab_state['running'] = running
    save_lab_data()
    
    print(f"🤖 ROBÔ {'LIGADO' if running else 'DESLIGADO'}")
    return jsonify({'success': True, 'running': running})


@app.route('/api/force_buy', methods=['POST'])
def force_buy():
    """⚡ COMPRA FORÇADA - Ignora indicadores, testa conexão com Binance."""
    if not exchange or not API_KEY or not SECRET:
        return jsonify({'success': False, 'error': '❌ Chaves API não configuradas!'}), 400
    
    data = request.json
    symbol = data.get('symbol', 'BTC/USDT')  # Padrão BTC/USDT
    amount_usd = 11.0  # Valor mínimo para teste
    
    try:
        print(f"{'='*60}")
        print(f"⚡ COMPRA FORÇADA INICIADA - {symbol}")
        print(f"{'='*60}")
        
        # Busca preço atual
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        
        # Calcula quantidade
        qty = amount_usd / current_price
        
        # Executa ordem de mercado
        order = exchange.create_market_buy_order(symbol, qty)
        
        print(f"✅ ORDEM EXECUTADA!")
        print(f"   ID: {order['id']}")
        print(f"   Preço: ${order.get('average', current_price):.2f}")
        print(f"   Quantidade: {order['filled']}")
        
        # Notifica no Telegram
        msg = f"⚡ *COMPRA FORÇADA (TESTE)*\n\n🪙 Moeda: {symbol}\n💰 Preço: ${current_price:.2f}\n📦 Qtd: {order['filled']}\n🆔 Order ID: {order['id']}"
        send_telegram_message(msg)
        
        # Registra na estratégia ativa
        strategy_key = lab_state['selected_strategy']
        trade = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': f'⚡ FORCE BUY ({symbol})',
            'price': order.get('average', current_price),
            'qty': order['filled'],
            'order_id': order['id'],
            'mode': 'REAL (TESTE)'
        }
        lab_state['strategies'][strategy_key]['trades'].append(trade)
        save_lab_data()
        
        return jsonify({
            'success': True,
            'message': f'✅ Compra executada! {order["filled"]} {symbol}',
            'order_id': order['id'],
            'price': order.get('average', current_price),
            'qty': order['filled']
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ ERRO NA COMPRA FORÇADA: {error_msg}")
        send_telegram_message(f"❌ *ERRO NA COMPRA FORÇADA*\n\n{error_msg}")
        return jsonify({'success': False, 'error': error_msg}), 500


@app.route('/api/export_data')
def export_data():
    """Exporta todos os dados do usuário da Binance."""
    if not exchange or not API_KEY or not SECRET:
        return jsonify({'error': 'API não configurada'}), 400

    try:
        # 1. Informações da Conta (Saldo detalhado)
        account_balance = exchange.fetch_balance()
        
        # 1.1 Informações da Conta (Dados brutos da Binance - Permissões, Comissões, etc)
        account_details = exchange.private_get_account()

        # 2. Histórico de Trades (Últimos trades do símbolo atual)
        trades = exchange.fetch_my_trades(SYMBOL)
        
        # 3. Ordens Abertas
        open_orders = exchange.fetch_open_orders(SYMBOL)
        
        # 4. Todas as Ordens (Histórico)
        all_orders = exchange.fetch_orders(SYMBOL)
        
        export_package = {
            'timestamp': datetime.now().isoformat(),
            'symbol': SYMBOL,
            'account_details_binance': account_details, # Dados brutos da conta
            'account_balance': account_balance,
            'my_trades': trades,
            'open_orders': open_orders,
            'order_history': all_orders,
            'note': 'Dados exportados via API Binance (CCXT)'
        }
        
        return jsonify(export_package)

    except Exception as e:
        print(f"❌ Erro ao exportar dados: {e}")
        # Retorna erro mas tenta enviar o que conseguiu ou mensagem clara
        return jsonify({'error': str(e)}), 500


# --- TELEGRAM BOT LISTENER (COMANDOS) ---

async def telegram_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Sou o Bot do Laboratório de Trading.\n\n"
        "Comandos disponíveis:\n"
        "/status - Ver preço e indicadores atuais\n"
        "/saldo - Ver saldo da conta\n"
        "/ajuda - Ver lista de comandos"
    )

async def telegram_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Comandos do Bot:*\n\n"
        "/status - Mostra o que o bot está analisando agora.\n"
        "/saldo - Mostra seu saldo em BRL e USDT.\n"
        "/start - Inicia o bot.",
        parse_mode='Markdown'
    )

async def telegram_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg = "📊 *STATUS DO MERCADO*\n\n"
        msg += f"🪙 *Moeda:* {lab_state['current_symbol']}\n"
        msg += f"💰 *Preço:* ${lab_state['current_price']:.2f}\n"
        msg += f"📉 *RSI:* {lab_state['indicators']['rsi']:.2f}\n"
        msg += f"🛡️ *Bandas:* {lab_state['indicators']['bb_lower']:.2f}\n\n"
        
        msg += f"⚙️ *Configuração:*\n"
        msg += f"Estratégia: {lab_state['selected_strategy']}\n"
        msg += f"Modo: Trading Real 💰\n"
        msg += f"Status: {lab_state['status']}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar status: {str(e)}")

async def telegram_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balances = lab_state['user_info'].get('balances', {})
        msg = "💰 *SEU SALDO*\n\n"
        if not balances:
            msg += "Nenhum saldo encontrado ou API desconectada."
        else:
            for coin, amount in balances.items():
                msg += f"• *{coin}:* {amount:.4f}\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar saldo: {str(e)}")

async def telegram_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a mensagens de texto usando GPT com contexto do mercado."""
    user_message = update.message.text
    print(f"📩 Mensagem recebida de {update.effective_user.first_name}: {user_message}")
    
    if not openai_client:
        await update.message.reply_text("🧠 IA não configurada no servidor.")
        return

    try:
        # Envia "Digitando..."
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Constrói contexto do mercado atual
        market_context = "DADOS ATUAIS DO MERCADO (Use isso para responder):\n"
        if lab_state['market_overview']:
            for symbol, data in lab_state['market_overview'].items():
                market_context += f"- {symbol}: Preço=${data['price']:.2f} | RSI={data['rsi']:.1f} | BB_Lower=${data['bb_lower']:.2f}\n"
        else:
            market_context += "Nenhum dado de mercado coletado ainda.\n"
            
        market_context += f"\nSaldo do Usuário: {lab_state.get('real_balance', 0):.2f}\n"
        market_context += f"Estratégia Ativa: {lab_state['selected_strategy']}\n"
        
        # Adiciona regras da estratégia e estado do modo real
        strategy_key = lab_state['selected_strategy']
        is_live = lab_state['is_live']
        
        strategy_rules = "Desconhecida"
        if strategy_key == 'conservative':
            strategy_rules = "Comprar APENAS quando RSI < 30 e Preço < Banda Inferior."
        elif strategy_key == 'aggressive':
            strategy_rules = "Comprar quando RSI < 45 e Preço < Banda Inferior."
        elif strategy_key == 'rsi_pure':
            strategy_rules = "Comprar quando RSI < 30."
            
        market_context += f"Modo: Trading Real 🚀\n"
        market_context += f"Regras da Estratégia Atual: {strategy_rules}\n"

        system_prompt = (
            "Você é um assistente de trading experiente e útil conectado a um bot em tempo real.\n"
            "Você TEM acesso aos dados atuais do mercado fornecidos abaixo.\n"
            "Use esses dados para responder perguntas sobre preços, tendências e se vale a pena comprar/vender.\n"
            "IMPORTANTE: Se o usuário perguntar 'por que não comprou nada' ou 'por que não tem operações', "
            "verifique se o RSI atual atende às regras da estratégia. Se o RSI estiver alto (ex: > 30 ou > 45), "
            "explique que o mercado não está em ponto de compra segundo a estratégia.\n"
            "Também verifique se o Modo Real está ativado.\n"
            "Responda de forma concisa, direta e use emojis.\n\n"
            f"{market_context}"
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=400
        )
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"❌ Erro na IA: {e}")
        await update.message.reply_text(f"❌ Erro na IA: {str(e)}")

def run_telegram_bot():
    """Inicia o bot do Telegram em modo de escuta (Polling)."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'your_telegram_token_here':
        print("⚠️ Telegram Listener não iniciado (Token inválido)")
        return

    # Cria novo loop de eventos para esta thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print("🤖 Iniciando Telegram Bot Listener...")
    
    try:
        app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        
        # Tenta enviar mensagem de boas-vindas para confirmar conexão
        if TELEGRAM_CHAT_ID:
            try:
                print(f"📨 Tentando enviar mensagem de teste para ID: {TELEGRAM_CHAT_ID}")
                loop.run_until_complete(app_bot.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🤖 *Bot Reiniciado!* Estou online e pronto para conversar.", parse_mode='Markdown'))
                print("✅ Mensagem de teste enviada com sucesso!")
            except Exception as e:
                print(f"❌ Falha ao enviar mensagem de teste: {e}")

        app_bot.add_handler(CommandHandler("start", telegram_start))
        app_bot.add_handler(CommandHandler("ajuda", telegram_help))
        app_bot.add_handler(CommandHandler("help", telegram_help))
        app_bot.add_handler(CommandHandler("status", telegram_status))
        app_bot.add_handler(CommandHandler("saldo", telegram_balance))
        
        # Handler para mensagens de texto (Chat com GPT)
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_chat))
        
        # stop_signals=None é necessário quando roda em uma thread secundária
        print("🤖 Telegram Bot ouvindo...")
        app_bot.run_polling(stop_signals=None, close_loop=False)
    except Exception as e:
        print(f"❌ Erro fatal no Telegram Bot: {e}")

# Inicia thread do Telegram Listener
telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
telegram_thread.start()

# Inicia thread de trading
thread = threading.Thread(target=trading_loop, daemon=True)
thread.start()


if __name__ == '__main__':
    print("="*60)
    print("🏗️  LABORATÓRIO DE TRADING HÍBRIDO")
    print("="*60)
    print(f"API Key: {API_KEY[:8] + '...' if API_KEY else 'NÃO CONFIGURADO'}")
    print(f"Secret: {'✓ Configurado' if SECRET else '✗ Não configurado'}")
    print(f"Símbolo: {SYMBOL}")
    print("="*60)
    app.run(host='0.0.0.0', debug=True, port=5000, use_reloader=False)
