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

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Configurações
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')
SYMBOL = os.getenv('SYMBOL', 'BTC/USDT')
AMOUNT_INVEST = float(os.getenv('AMOUNT_INVEST', 11.0))
FEE_RATE = 0.001  # 0.1%

# Estado Global
lab_state = {
    'strategies': {
        'conservative': {'name': 'Conservador 🛡️', 'balance': 100.0, 'trades': [], 'position': None},
        'aggressive': {'name': 'Agressivo 🚀', 'balance': 100.0, 'trades': [], 'position': None},
        'rsi_pure': {'name': 'RSI Puro 🎯', 'balance': 100.0, 'trades': [], 'position': None}
    },
    'selected_strategy': 'conservative',
    'is_live': False,
    'real_balance': 0.0,
    'last_update': '',
    'current_price': 0.0,
    'status': 'Rodando',
    'user_info': {
        'uid': '---',
        'type': '---',
        'can_trade': False,
        'balances': {}
    }
}

# Exchange
exchange = None
try:
    exchange_config = {
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
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
    print("✅ Exchange conectada")
except Exception as e:
    print(f"⚠️ Exchange modo simulação: {e}")


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


def fetch_market_data():
    """Busca dados de mercado para análise."""
    try:
        if not exchange:
            return None, None, None

        # Busca últimas 100 velas de 5 minutos
        ohlcv = exchange.fetch_ohlcv(SYMBOL, '5m', limit=100)
        closes = [candle[4] for candle in ohlcv]
        current_price = closes[-1]

        rsi = calculate_rsi(closes)
        upper, sma, lower = calculate_bollinger(closes)

        return current_price, rsi, lower
    except Exception as e:
        print(f"❌ Erro ao buscar dados: {e}")
        print("⚠️ ATENÇÃO: Usando dados SIMULADOS devido a erro na API (Restrição de IP ou Falha)")
        
        # Gera dados aleatórios para manter o sistema rodando
        last_price = lab_state.get('current_price', 0)
        if last_price == 0: last_price = 65000.0 # Preço base BTC
        
        # Variação aleatória de -0.1% a +0.1%
        variation = random.uniform(-0.001, 0.001)
        current_price = last_price * (1 + variation)
        
        # RSI aleatório mas com tendência
        rsi = random.uniform(20, 80)
        
        # Banda inferior simulada
        lower = current_price * 0.99
        
        return current_price, rsi, lower


def check_strategy_signal(strategy_name, price, rsi, bb_lower):
    """Verifica se a estratégia dá sinal de compra."""
    if strategy_name == 'conservative':
        return rsi < 30 and price < bb_lower
    elif strategy_name == 'aggressive':
        return rsi < 45 and price < bb_lower
    elif strategy_name == 'rsi_pure':
        return rsi < 30
    return False


def check_exit_signal(entry_price, current_price, rsi):
    """Verifica sinal de saída."""
    profit_pct = ((current_price - entry_price) / entry_price) * 100

    # Lucro > 1.5% OU Stop < -1.5% OU RSI > 70
    return profit_pct > 1.5 or profit_pct < -1.5 or rsi > 70


def simulate_trade(strategy_key, action, price):
    """Executa trade simulado."""
    strategy = lab_state['strategies'][strategy_key]

    if action == 'buy' and strategy['position'] is None:
        qty = (AMOUNT_INVEST / price) * (1 - FEE_RATE)
        strategy['position'] = {
            'entry_price': price, 'qty': qty, 'entry_time': datetime.now().isoformat()}
        strategy['balance'] -= AMOUNT_INVEST

        trade = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'BUY',
            'price': price,
            'qty': qty,
            'mode': 'SIM'
        }
        strategy['trades'].append(trade)
        print(f"🔵 [{strategy['name']}] COMPRA SIM: {qty:.8f} @ ${price:.2f}")

    elif action == 'sell' and strategy['position'] is not None:
        pos = strategy['position']
        sell_value = (pos['qty'] * price) * (1 - FEE_RATE)
        strategy['balance'] += sell_value

        profit = sell_value - AMOUNT_INVEST
        profit_pct = (profit / AMOUNT_INVEST) * 100

        trade = {
            'time': datetime.now().strftime('%H:%M:%S'),
            'type': 'SELL',
            'price': price,
            'qty': pos['qty'],
            'profit': profit,
            'profit_pct': profit_pct,
            'mode': 'SIM'
        }
        strategy['trades'].append(trade)
        strategy['position'] = None
        print(f"🟢 [{strategy['name']}] VENDA SIM: {pos['qty']:.8f} @ ${price:.2f} | Lucro: ${profit:.2f} ({profit_pct:+.2f}%)")


def execute_real_trade(action, price):
    """Executa trade REAL na Binance."""
    if not exchange or not API_KEY or not SECRET:
        print("⚠️ Modo real desabilitado: sem chaves API")
        return False

    try:
        strategy_key = lab_state['selected_strategy']
        strategy = lab_state['strategies'][strategy_key]

        if action == 'buy':
            # Ordem de compra REAL
            order = exchange.create_market_buy_order(
                SYMBOL, AMOUNT_INVEST / price)

            trade = {
                'time': datetime.now().strftime('%H:%M:%S'),
                'type': 'BUY REAL',
                'price': order['average'] or price,
                'qty': order['filled'],
                'order_id': order['id'],
                'mode': 'REAL'
            }
            strategy['trades'].append(trade)
            print(
                f"💰 [{strategy['name']}] COMPRA REAL: {order['filled']} @ ${order['average']:.2f}")
            return True

        elif action == 'sell':
            # Busca posição aberta para saber quanto vender
            if strategy['position']:
                qty = strategy['position']['qty']
                order = exchange.create_market_sell_order(SYMBOL, qty)

                trade = {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'type': 'SELL REAL',
                    'price': order['average'] or price,
                    'qty': order['filled'],
                    'order_id': order['id'],
                    'mode': 'REAL'
                }
                strategy['trades'].append(trade)
                print(
                    f"💵 [{strategy['name']}] VENDA REAL: {order['filled']} @ ${order['average']:.2f}")
                return True

    except Exception as e:
        print(f"❌ ERRO ORDEM REAL: {e}")
        return False


def trading_loop():
    """Loop principal do sistema."""
    print("🚀 Loop de trading iniciado")
    load_lab_data()

    while True:
        try:
            # 1. Busca dados de mercado
            price, rsi, bb_lower = fetch_market_data()

            if price is None:
                time.sleep(10)
                continue

            lab_state['current_price'] = price
            lab_state['last_update'] = datetime.now().strftime('%H:%M:%S')

            # 2. Simulação: Testa todas as 3 estratégias
            for strategy_key in lab_state['strategies'].keys():
                strategy = lab_state['strategies'][strategy_key]

                # Verifica sinal de COMPRA
                if strategy['position'] is None:
                    if check_strategy_signal(strategy_key, price, rsi, bb_lower):
                        simulate_trade(strategy_key, 'buy', price)

                # Verifica sinal de VENDA
                elif strategy['position'] is not None:
                    entry_price = strategy['position']['entry_price']
                    if check_exit_signal(entry_price, price, rsi):
                        simulate_trade(strategy_key, 'sell', price)

            # 3. Modo Real: Executa APENAS a estratégia selecionada
            if lab_state['is_live']:
                selected = lab_state['selected_strategy']
                strategy = lab_state['strategies'][selected]

                if strategy['position'] is None:
                    if check_strategy_signal(selected, price, rsi, bb_lower):
                        execute_real_trade('buy', price)
                else:
                    entry_price = strategy['position']['entry_price']
                    if check_exit_signal(entry_price, price, rsi):
                        execute_real_trade('sell', price)

            # 4. Atualiza saldo real e informações da conta
            if exchange and API_KEY:
                try:
                    # Busca informações detalhadas da conta (UID, Permissões)
                    # Nota: private_get_account é específico da Binance
                    account_info = exchange.private_get_account()
                    
                    lab_state['user_info']['uid'] = account_info.get('uid', 'Não informado')
                    lab_state['user_info']['type'] = account_info.get('accountType', 'SPOT')
                    lab_state['user_info']['can_trade'] = account_info.get('canTrade', False)

                    # Busca saldos
                    balance = exchange.fetch_balance()
                    lab_state['real_balance'] = balance['total'].get('USDT', 0.0)
                    
                    # Filtra saldos > 0 para exibir
                    relevant_balances = {}
                    for asset, amount in balance['total'].items():
                        if amount > 0:
                            relevant_balances[asset] = amount
                    lab_state['user_info']['balances'] = relevant_balances

                except Exception as e:
                    # Em caso de erro (ex: IP bloqueado), mantém os dados anteriores ou mostra erro
                    # print(f"⚠️ Erro ao atualizar conta: {e}") # Comentado para não poluir log
                    pass


            # 5. Salva estado
            save_lab_data()

            time.sleep(5)  # Aguarda 5 segundos

        except Exception as e:
            print(f"❌ Erro no loop: {e}")
            time.sleep(10)


# Rotas da API
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Retorna estado completo do laboratório."""
    return jsonify(lab_state)


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


@app.route('/api/export_data')
def export_data():
    """Exporta todos os dados do usuário da Binance."""
    if not exchange or not API_KEY or not SECRET:
        return jsonify({'error': 'API não configurada'}), 400

    try:
        # 1. Informações da Conta
        account_info = exchange.fetch_balance()
        
        # 2. Histórico de Trades (Últimos trades do símbolo atual)
        trades = exchange.fetch_my_trades(SYMBOL)
        
        # 3. Ordens Abertas
        open_orders = exchange.fetch_open_orders(SYMBOL)
        
        # 4. Todas as Ordens (Histórico)
        all_orders = exchange.fetch_orders(SYMBOL)

        # 5. Tenta buscar dados extras (Allocations, Prevented Matches) se possível
        # Nota: ccxt pode não ter métodos diretos para tudo, usamos private_get se necessário
        # Mas para simplificar e garantir compatibilidade, focamos no principal.
        
        export_package = {
            'timestamp': datetime.now().isoformat(),
            'symbol': SYMBOL,
            'account_balance': account_info,
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
