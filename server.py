"""Servidor do bot (Flask + Telegram + loop de trading)."""

SANDRA_PROMPT = """PROMPT DA IA – MODO ASSESSORA FINANCEIRA (CEO do Sistema)

Você é a Sandra, a Gerente Executiva e Assessora Financeira do Jonatas.
Sua missão é gerenciar o capital com precisão cirúrgica e fornecer dados exatos sempre que solicitada.

PERFIL:
- Tom de voz: Profissional, educada, eficiente e direta.
- Atitude: Você trabalha para o Jonatas. Se ele pedir um cálculo, você entrega os números detalhados.
- Foco: Proteção de capital e clareza nos relatórios.

REGRAS DE OPERAÇÃO:
1. Entrada: RSI <35 (5min) com preço na banda inferior. Tolerância 1%.
   - Se o cenário for perfeito (RSI <25), sugira aumentar a mão para $22 ou $33.
2. Saída: Busque lucro de 5%. Se explodir rápido, ative Trailing Stop de 3%.
   - Segurança máxima: Se RSI passar de 65, venda para garantir o lucro.
3. Proteção: Se o saldo cair 10%, entre em modo defensivo (reduza para $8).

REGRAS DE COMUNICAÇÃO (TELEGRAM):
- Quando o Jonatas perguntar sobre uma moeda, traga os dados: Preço Médio de Compra, Valor Atual e Lucro/Prejuízo em tempo real.
- Exemplo de resposta ideal:
  "Sr. Jonatas, comprei ADA a $0.3500. Agora está $0.3550.
   Se vender neste momento, seu lucro líquido estimado é de +$0.15 (1.4%).
   Deseja que eu execute a venda?"

Objetivo: Fazer o patrimônio crescer com segurança e manter o chefe informado com dados reais.
"""

import os
import json
import time
import random
import re
import threading
import tempfile
import copy
import queue
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, render_template, request, abort
from dotenv import load_dotenv
import ccxt
import numpy as np
import requests
import asyncio
import io
import matplotlib
matplotlib.use('Agg') # Backend não interativo
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import scalper_blindado
import ceo_manager

import logging
import traceback
from logging.handlers import RotatingFileHandler

# Relatórios por e-mail (std lib) + leitura do SQLite
try:
    from reporting import build_daily_summary, format_daily_summary_text, send_email_smtp
except Exception:
    build_daily_summary = None
    format_daily_summary_text = None
    send_email_smtp = None

# Backup/rotação do SQLite (snapshot consistente)
try:
    from db_backup import backup_sqlite_db, env_truthy as _env_truthy_db
except Exception:
    backup_sqlite_db = None
    _env_truthy_db = None

# Configuração de Logs (rotativo para não estourar disco)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Evita que bibliotecas de HTTP loguem URLs completas (pode vazar tokens em endpoints do Telegram)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.WARNING)

_root_logger = logging.getLogger()
_rot_handler = RotatingFileHandler(
    'sistema_trading.log',
    maxBytes=5_000_000,
    backupCount=5,
    encoding='utf-8'
)
_rot_handler.setLevel(logging.INFO)
_rot_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
_root_logger.addHandler(_rot_handler)

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)

# Lock global para evitar race condition entre threads (Flask/trading/Telegram)
state_lock = threading.RLock()

# Lock dedicado para serializar chamadas no mesmo client CCXT (evita race/nonce/rate-limit)
exchange_lock = threading.RLock()


def ex(fn, *args, **kwargs):
    """Serializa chamadas no client CCXT compartilhado."""
    with exchange_lock:
        return fn(*args, **kwargs)


@app.errorhandler(401)
def _unauthorized(_err):
    return jsonify({'error': 'unauthorized'}), 401


# Token simples para proteger rotas perigosas (produção)
API_TOKEN = os.getenv('API_TOKEN', '').strip()
if os.getenv("ENV", "dev") == "prod" and not API_TOKEN:
    raise RuntimeError("API_TOKEN obrigatório em produção.")


def _require_api_token_if_configured():
    """Exige token apenas se API_TOKEN estiver definido no ambiente."""
    if not API_TOKEN:
        return

    provided = (
        request.headers.get('X-API-Token')
        or request.args.get('token')
        or ''
    ).strip()

    if not provided:
        auth = (request.headers.get('Authorization') or '').strip()
        if auth.lower().startswith('bearer '):
            provided = auth[7:].strip()

    if not provided or provided != API_TOKEN:
        abort(401)


@app.before_request
def protect_api():
    # Se API_TOKEN estiver configurado, protege tudo em /api/
    if request.path.startswith('/api/'):
        _require_api_token_if_configured()


# Cache TTL simples para chamadas privadas caras (evita rate-limit)
_ttl_cache_lock = threading.RLock()
_ttl_cache: dict[str, dict] = {}


def _ttl_cached_call(cache_key: str, ttl_s: float, fn):
    now_mono = time.monotonic()
    with _ttl_cache_lock:
        entry = _ttl_cache.get(cache_key)
        if entry and (now_mono - entry['ts']) <= ttl_s:
            return entry['value']

    try:
        value = fn()
    except Exception:
        # Se der erro, tenta devolver cache antigo (se existir)
        with _ttl_cache_lock:
            entry = _ttl_cache.get(cache_key)
            if entry:
                return entry['value']
        raise

    with _ttl_cache_lock:
        _ttl_cache[cache_key] = {'ts': now_mono, 'value': value}
    return value


_http_session = requests.Session()


def _http_get_json(url: str, params: dict | None = None, timeout: int = 10, retries: int = 2):
    """GET com retry simples para erros transitórios (Binance)."""
    backoff = 1.5
    last_err = None
    for attempt in range(retries + 1):
        try:
            response = _http_session.get(url, params=params, timeout=timeout)
            if response.status_code in (418, 429, 500, 502, 503, 504):
                last_err = RuntimeError(f"HTTP {response.status_code}: {response.text}")
            else:
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_err = e

        if attempt < retries:
            time.sleep(backoff ** attempt)

    raise last_err


def cached_fetch_balance(ttl_s: float = 3.0):
    if not exchange:
        raise RuntimeError('Exchange não conectada')
    return _ttl_cached_call('fetch_balance', ttl_s, lambda: ex(exchange.fetch_balance))


def cached_private_get_account(ttl_s: float = 10.0):
    if not exchange:
        raise RuntimeError('Exchange não conectada')
    return _ttl_cached_call('private_get_account', ttl_s, lambda: ex(exchange.private_get_account))


def get_public_snapshot() -> dict:
    """Snapshot consistente do estado para rotas de leitura (evita races)."""
    with state_lock:
        return copy.deepcopy(lab_state)


@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# Configurações
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')
TELEGRAM_TOKEN = (os.getenv('TELEGRAM_TOKEN') or '').strip()
TELEGRAM_CHAT_ID = (os.getenv('TELEGRAM_CHAT_ID') or '').strip()
TELEGRAM_CHAT_IDS = (os.getenv('TELEGRAM_CHAT_IDS') or '').strip()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not API_KEY or API_KEY == 'sua_api_key_aqui':
    print("\n" + "="*50)
    print("❌ AVISO: CHAVES DE API NÃO ENCONTRADAS")
    print("👉 Edite o arquivo .env e coloque suas chaves da Binance")
    print("="*50 + "\n")

SYMBOL = os.getenv('SYMBOL', 'BTC/USDT')
AMOUNT_INVEST = float(os.getenv('AMOUNT_INVEST', 11.0))
FEE_RATE = 0.001  # 0.1%

# 💰 JURO COMPOSTO: Saldo base para escalar apostas automaticamente
# À medida que o saldo cresce, as apostas aumentam proporcionalmente
SALDO_BASE = float(os.getenv('SALDO_BASE', 100.0))  # Saldo inicial da conta

# Configuração GPT (controle de uso)
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
ENABLE_GPT_TUNING = os.getenv('ENABLE_GPT_TUNING', 'false').lower() == 'true'

# Timezone padrão (evita relatórios fora do horário em servidor UTC)
TZ = ZoneInfo("America/Sao_Paulo")


def now_sp() -> datetime:
    return datetime.now(TZ)


def now_iso() -> str:
    return now_sp().isoformat()


def parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt
    except Exception:
        return None

# Parâmetros de estratégia AJUSTÁVEIS pela IA
STRATEGY_PARAMS = {
    'RSI_TARGET': 35,        # RSI para compra
    'TOLERANCE': 0.01,       # Tolerância da banda (1%)
    'STOP_LOSS': -3.0,       # Stop loss em %
    'TAKE_PROFIT': 5.0,      # Take profit em %
}

# Configuração OpenAI (retry em falha temporária)
openai_client = None
_openai_last_fail = 0.0


def get_openai_client():
    """Inicializa OpenAI client sob demanda; re-tenta a cada 60s se falhar."""
    global openai_client, _openai_last_fail

    if openai_client:
        return openai_client

    if not OPENAI_API_KEY or OPENAI_API_KEY == 'your_openai_api_key_here':
        return None

    if time.time() - _openai_last_fail < 60:
        return None

    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        print("🧠 OpenAI (GPT) Configurado")
        return openai_client
    except Exception as e:
        _openai_last_fail = time.time()
        print(f"⚠️ Erro ao configurar OpenAI: {e}")
        return None


def openai_text(
    instructions: str,
    user_input: str,
    max_output_tokens: int = 400,
    temperature: float = 0.3,
) -> str:
    client = get_openai_client()
    if not client:
        return "🧠 IA não configurada no servidor."

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_input},
        ],
        max_tokens=max_output_tokens,
        temperature=temperature,
    )
    return (resp.choices[0].message.content or "").strip()

# App do Telegram (criado no main antes das threads)
telegram_app = None

# Estado Global
lab_state = {
    'strategies': {
        'aggressive': {'name': 'Trading Real 💰 (Sandra)', 'balance': 0.0, 'trades': [], 'position': None},
        'aggressive_parcial': {'name': 'Trading Agressivo 🔥 (Parcial)', 'balance': 0.0, 'trades': [], 'position': None}
    },
    'selected_strategy': 'aggressive',  # Padrão: Sandra Mode
    'is_live': True,  # Valor inicial (pode ser sobrescrito por lab_data.json e/ou rotas)
    'running': True,  # Valor inicial (pode ser sobrescrito por lab_data.json e/ou rotas)
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
    'last_trade_time': 0,  # Cooldown global (Sandra usa isso)
    'symbol_cooldowns': {},  # Cooldown por símbolo (aggressive_parcial usa isso: 15min)
    'pnl': {  # Sandra Mode: Tracking de lucro diário
        'date': now_sp().strftime('%Y-%m-%d'),
        'day_net': 0.0,
        'total_net': 0.0
    },
    'btc_red_days': 0,  # Contador de dias vermelhos consecutivos do BTC
    'streak': {'wins': 0, 'losses': 0, 'tight': False}  # Sandra streak tracking
}

# Exchange
exchange = None
try:
    # Primeiro, obtém a diferença de tempo com o servidor da Binance
    exchange_temp = ccxt.binance({'enableRateLimit': True})
    time_diff = 0
    for i in range(3):
        try:
            server_time = exchange_temp.fetch_time()
            local_time = int(time.time() * 1000)
            time_diff = server_time - local_time
            print(f"⏰ Sincronizando tempo: diferença de {time_diff}ms com servidor Binance")
            break
        except Exception as e:
            print(f"⚠️ Tentativa {i+1} de sincronizar tempo falhou: {e}")
            time.sleep(1)
    
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
    public_exchange = ccxt.binance({'enableRateLimit': True}) # Instância pública para fallback

    # Carrega markets para suportar exchange.market(symbol)/limits (min notional, precisões, etc.)
    try:
        exchange.load_markets()
    except Exception as e:
        print(f"⚠️ Não foi possível carregar markets da Binance agora: {e}")
    
    # Força sincronização de tempo
    print("⏳ Sincronizando relógio com a Binance...")
    diff = exchange.load_time_difference()
    print(f"✅ Relógio sincronizado. Diferença: {diff}ms")
    
    print("✅ Exchange conectada")
except Exception as e:
    print(f"⚠️ Erro ao conectar Exchange: {e}")


# ==============================================================================
# 🗄️ PERSISTÊNCIA BLINDADA (SQLite - O Cérebro de Aço da Sandra)
# ==============================================================================

DB_FILE = 'sandra_trading.db'

# Suporte a layout organizado (sem quebrar instalações antigas)
PROJECT_DATA_DIR = os.getenv('PROJECT_DATA_DIR', 'data').strip() or 'data'


def _get_legacy_json_path():
    """Retorna o caminho do JSON legado, se existir.

    Mantém compatibilidade com versões antigas (arquivo na raiz) e layout organizado
    (arquivo em data/legacy/).
    """
    candidates = [
        'lab_data.json',
        os.path.join(PROJECT_DATA_DIR, 'legacy', 'lab_data.json'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def init_db():
    """Inicializa o banco de dados e cria tabelas se não existirem."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabela para configurações e estado atual (JSON blob para flexibilidade)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Tabela para Histórico Eterno de Trades (Relatórios futuros)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy TEXT,
            symbol TEXT,
            side TEXT,
            price REAL,
            qty REAL,
            profit_usdt REAL,
            profit_pct REAL,
            timestamp TEXT,
            json_data TEXT
        )
    ''')

    # Eventos importantes do sistema (auditoria leve; sem spam)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            event_type TEXT,
            message TEXT,
            json_data TEXT
        )
    ''')
    conn.commit()
    return conn


def db_record_trade(strategy_name: str, trade: dict) -> None:
    """Grava BUY/SELL no trade_history (histórico eterno) e não derruba o bot."""
    try:
        side = str(trade.get('side', 'unknown'))
        symbol = str(trade.get('symbol', ''))
        # Para BUY: usa trade['price']; para SELL: usa trade['exit_price'] se existir
        price = float(trade.get('exit_price') or trade.get('price') or 0)
        qty = float(trade.get('qty') or 0)
        profit_usdt = float(trade.get('net_profit_usdt') or 0)
        profit_pct = float(trade.get('net_profit_pct') or trade.get('profit_pct') or 0)
        ts = str(trade.get('timestamp') or now_iso())

        conn = sqlite3.connect(DB_FILE, timeout=30)
        try:
            cur = conn.cursor()
            cur.execute(
                '''
                INSERT INTO trade_history (strategy, symbol, side, price, qty, profit_usdt, profit_pct, timestamp, json_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    strategy_name,
                    symbol,
                    side,
                    price,
                    qty,
                    profit_usdt,
                    profit_pct,
                    ts,
                    json.dumps(trade, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        print(f"⚠️ Falha ao gravar trade_history: {e}")


def db_record_event(event_type: str, message: str, level: str = 'INFO', data: dict | None = None) -> None:
    """Registra evento importante no SQLite (audit trail)."""
    try:
        conn = sqlite3.connect(DB_FILE, timeout=30)
        try:
            cur = conn.cursor()
            cur.execute(
                '''
                INSERT INTO system_events (timestamp, level, event_type, message, json_data)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    now_iso(),
                    str(level),
                    str(event_type),
                    str(message),
                    json.dumps(data, ensure_ascii=False) if data else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Evento é best-effort, nunca derruba.
        pass


def maybe_backup_db(reason: str = '') -> None:
    """Backup automático do DB (snapshot). Controlado por env vars.

    - DB_BACKUP_ENABLED (default true)
    - DB_BACKUP_DIR (default backups)
    - DB_BACKUP_KEEP_LAST (default 50)
    """
    if not backup_sqlite_db or not _env_truthy_db:
        return

    enabled = _env_truthy_db('DB_BACKUP_ENABLED', default=True)
    if not enabled:
        return

    backup_dir = os.getenv('DB_BACKUP_DIR', 'backups').strip() or 'backups'
    try:
        keep_last = int(os.getenv('DB_BACKUP_KEEP_LAST', '50') or 50)
    except Exception:
        keep_last = 50

    try:
        path = backup_sqlite_db(DB_FILE, backup_dir=backup_dir, keep_last=keep_last)
        db_record_event('db_backup', f"Backup SQLite criado: {os.path.basename(path)}", data={'reason': reason})
    except Exception as e:
        db_record_event('db_backup_error', f"Falha no backup SQLite: {e}", level='WARN', data={'reason': reason})

def migrate_json_to_db():
    """Importa o JSON antigo para o DB na primeira execução."""
    legacy_json = _get_legacy_json_path()
    if legacy_json and not os.path.exists(DB_FILE):
        print("📦 Migrando dados antigos do JSON para SQLite...")
        try:
            conn = init_db()
            with open(legacy_json, 'r') as f:
                data = json.load(f)
            
            # Salva estado atual
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)', 
                          ('lab_state', json.dumps(data)))
            
            # Tenta extrair trades antigos para o histórico
            strategies = data.get('strategies', {})
            count = 0
            for strat_name, strat_data in strategies.items():
                trades = strat_data.get('trades', [])
                for t in trades:
                    cursor.execute('''
                        INSERT INTO trade_history (strategy, symbol, side, price, qty, profit_usdt, profit_pct, timestamp, json_data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        strat_name,
                        t.get('symbol'),
                        t.get('side', 'unknown'),
                        float(t.get('price', 0) or 0),
                        float(t.get('qty', 0) or 0),
                        float(t.get('net_profit_usdt', 0) or 0),
                        float(t.get('profit_pct', 0) or 0),
                        t.get('timestamp', now_iso()),
                        json.dumps(t)
                    ))
                    count += 1
            
            conn.commit()
            conn.close()
            print(f"✅ Migração concluída! {count} trades salvos no banco.")
            # Renomeia o JSON para backup para não confundir
            legacy_dir = os.path.dirname(legacy_json) or '.'
            backup_path = os.path.join(legacy_dir, 'lab_data_backup.json')
            os.replace(legacy_json, backup_path)
        except Exception as e:
            print(f"⚠️ Erro na migração (dados mantidos no JSON): {e}")

def load_lab_data():
    """Carrega dados do SQLite para a memória."""
    global lab_state
    
    # Verifica se precisa migrar antes de carregar
    if _get_legacy_json_path() and not os.path.exists(DB_FILE):
        migrate_json_to_db()

    try:
        conn = init_db()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM system_state WHERE key = ?', ('lab_state',))
        row = cursor.fetchone()
        
        if row:
            data = json.loads(row[0])
            with state_lock:
                # Restaura estado principal
                lab_state['strategies'] = data.get('strategies', lab_state['strategies'])
                lab_state['selected_strategy'] = data.get('selected_strategy', 'aggressive')
                
                # Valida se a strategy existe
                if lab_state['selected_strategy'] not in lab_state['strategies']:
                    print(f"⚠️ Strategy '{lab_state['selected_strategy']}' não existe, usando 'aggressive'")
                    lab_state['selected_strategy'] = 'aggressive'
                
                lab_state['is_live'] = data.get('is_live', False)
                lab_state['running'] = data.get('running', False)
                lab_state['pnl'] = data.get('pnl', lab_state.get('pnl', {}))
                lab_state['streak'] = data.get('streak', lab_state.get('streak', {}))

                # Caçador (persistência leve)
                dyn = data.get('dynamic_watchlist')
                if isinstance(dyn, list):
                    lab_state['dynamic_watchlist'] = dyn
                lht = data.get('last_hunt_time')
                if lht is not None:
                    lab_state['last_hunt_time'] = lht

                jc = data.get('judge_cache')
                if isinstance(jc, dict):
                    lab_state['judge_cache'] = jc
                
                # Restaura estatísticas globais
                gs = data.get('global_stats')
                if isinstance(gs, dict):
                    GLOBAL_STATS.update(gs)
            print("📂 Dados carregados do Banco de Dados (SQLite)")
        else:
            print("📝 Banco novo criado (sem dados anteriores)")
            save_lab_data() # Cria estrutura inicial
        
        conn.close()
    except Exception as e:
        print(f"⚠️ Erro ao carregar do DB: {e}")
        # Fallback de segurança: cria estado novo se der pau violento
        save_lab_data()

def save_lab_data():
    """Salva estado atual no SQLite (Transacional e Seguro)."""
    with state_lock:
        # 1. Mantém apenas os últimos 200 trades na memória RAM para o bot ficar leve
        # (O histórico completo já vai estar no DB se implementarmos logica de insert individual, 
        # mas por segurança aqui salvamos o dump do estado atual)
        max_ram_trades = 200
        snapshot_data = copy.deepcopy(lab_state) # Cópia para não travar a thread
        
        # Limpa trades antigos da memória RAM antes de salvar o snapshot json
        # (Isso evita que o JSON dentro do banco fique gigante desnecessariamente)
        for _sk, _s in snapshot_data.get('strategies', {}).items():
            trades = _s.get('trades', [])
            if len(trades) > max_ram_trades:
                _s['trades'] = trades[-max_ram_trades:]

        data_to_save = {
            'strategies': snapshot_data['strategies'],
            'selected_strategy': snapshot_data['selected_strategy'],
            'is_live': snapshot_data['is_live'],
            'running': snapshot_data['running'],
            'pnl': snapshot_data.get('pnl', {}),
            'streak': snapshot_data.get('streak', {}),
            'dynamic_watchlist': snapshot_data.get('dynamic_watchlist', []),
            'last_hunt_time': snapshot_data.get('last_hunt_time', 0),
            'judge_cache': snapshot_data.get('judge_cache', {}),
            'global_stats': GLOBAL_STATS,
            'last_save': now_iso()
        }

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Salva o JSON principal
        cursor.execute('INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)', 
                      ('lab_state', json.dumps(data_to_save, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Erro crítico ao salvar no DB: {e}")

# ==============================================================================


def calculate_rsi(prices, period=14):
    """Calcula RSI (Wilder)."""
    if len(prices) < period + 1:
        return 50

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))

    for i in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


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

_telegram_queue: "queue.Queue[str]" = queue.Queue(maxsize=1000)
_telegram_worker_lock = threading.Lock()
_telegram_worker_started = False


def _get_telegram_chat_ids() -> list[object]:
    """Normaliza chat IDs do .env (suporta lista separada por vírgula)."""
    raw = TELEGRAM_CHAT_IDS or TELEGRAM_CHAT_ID
    if not raw:
        return []

    chat_ids: list[object] = []
    for part in raw.split(','):
        value = part.strip()
        if not value:
            continue
        if re.fullmatch(r"-?\d+", value):
            chat_ids.append(int(value))
        else:
            chat_ids.append(value)
    return chat_ids


def _split_telegram_message(text: str, limit: int = 3500) -> list[str]:
    """Divide mensagens longas para evitar erro 400 'message is too long'.

    Tenta quebrar em '\n' para preservar leitura; se necessário, faz corte bruto.
    """
    if not text:
        return ['']
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break

        cut = remaining.rfind('\n', 0, limit)
        if cut <= 0:
            cut = limit
        chunk = remaining[:cut].rstrip()
        if chunk:
            parts.append(chunk)
        remaining = remaining[cut:].lstrip('\n')

    return parts


def _send_telegram_message_now(message: str) -> None:
    """Envia mensagem para o Telegram (chamada no worker)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = _get_telegram_chat_ids()
    if not chat_ids:
        print("⚠️ Telegram sem chat_id válido. Mensagem descartada.")
        logging.warning("Telegram sem chat_id válido; mensagem descartada.")
        return

    def _escape_md_basic(text: str) -> str:
        # Markdown (Telegram): escapa caracteres que mais quebram mensagens
        # sem quebrar o uso atual de '*' para negrito.
        return re.sub(r"([_\[\]`])", r"\\\1", text)

    for chat_id in chat_ids:
        payload = {
            "chat_id": chat_id,
            "text": _escape_md_basic(message),
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        response = None
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("📨 Mensagem Telegram enviada com sucesso!")
                logging.info("Mensagem Telegram enviada com sucesso.")
                continue
        except Exception:
            response = None

        # Se falhar com Markdown, tenta enviar em texto puro
        try:
            payload_no_md = {
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            retry = requests.post(url, json=payload_no_md, timeout=10)
            if retry.status_code == 200:
                print("📨 Mensagem Telegram enviada (sem Markdown)")
                logging.info("Mensagem Telegram enviada (sem Markdown).")
            else:
                print(f"❌ Erro Telegram: {retry.text}")
                logging.error("Erro Telegram: %s", retry.text)
        except Exception as e:
            if response is not None:
                print(f"❌ Erro Telegram: {response.text}")
                logging.error("Erro Telegram: %s", response.text)
            else:
                print(f"❌ Erro ao enviar Telegram: {e}")
                logging.error("Erro ao enviar Telegram: %s", e)


def _telegram_worker() -> None:
    while True:
        message = _telegram_queue.get()
        try:
            _send_telegram_message_now(message)
        finally:
            _telegram_queue.task_done()


def _ensure_telegram_worker() -> None:
    global _telegram_worker_started
    with _telegram_worker_lock:
        if _telegram_worker_started:
            return
        thread = threading.Thread(target=_telegram_worker, daemon=True)
        thread.start()
        _telegram_worker_started = True


def send_telegram_message(message: str) -> None:
    """Envia mensagem para o Telegram (fila assíncrona)."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'your_telegram_token_here' or not _get_telegram_chat_ids():
        print("⚠️ Telegram não configurado. Mensagem não enviada.")
        return

    _ensure_telegram_worker()
    for part in _split_telegram_message(message, limit=3500):
        try:
            _telegram_queue.put_nowait(part)
        except queue.Full:
            print("⚠️ Fila do Telegram cheia, mensagem descartada.")
            return


# ==================== SISTEMA DE RELATÓRIOS AUTOMÁTICOS ====================

# Horários para enviar relatórios (formato 24h)
REPORT_HOURS = [8, 12, 18, 22]  # 8h, 12h, 18h, 22h
last_report_hour = -1  # Controle para não repetir relatório na mesma hora

def generate_market_report():
    """Gera relatório completo de todas as moedas."""
    snap = get_public_snapshot()
    report_lines = []
    report_lines.append("📊 *RELATÓRIO DO BOT DE TRADING*")
    report_lines.append(f"🕐 {now_sp().strftime('%d/%m/%Y %H:%M')}")
    report_lines.append("")
    
    # Status do bot
    status = "🟢 ATIVO" if snap.get('running') else "🔴 PARADO"
    mode = "💰 REAL" if snap.get('is_live') else "🧪 SIMULAÇÃO"
    report_lines.append(f"*Status:* {status} | {mode}")

    # Modo do Scalper (para transparência)
    try:
        cfg = getattr(scalper_blindado, 'CONFIG', {}) or {}
        rsi_gate = cfg.get('RSI_GATILHO', 'N/A')
        adx_max = cfg.get('ADX_MAXIMO', 'N/A')
        report_lines.append(f"*Scalper:* 🦅 SNIPER | RSI<{rsi_gate} | ADX<{adx_max} | sem filtro ATR")
    except Exception:
        pass
    
    # Saldo
    usdt = snap.get('real_balance', 0)
    report_lines.append(f"*Saldo USDT:* ${usdt:.2f}")
    report_lines.append("")
    
    # Posição atual
    selected = snap.get('selected_strategy', 'aggressive')
    strategy = snap.get('strategies', {}).get(selected, {})
    positions_dict = strategy.get('positions') if isinstance(strategy.get('positions'), dict) else {}
    position = None
    pos_count = 0

    if positions_dict:
        pos_count = len(positions_dict)
        first_symbol = next(iter(positions_dict))
        position = positions_dict.get(first_symbol)
    else:
        position = strategy.get('position')
    
    if position:
        pos_symbol = position.get('symbol', 'N/A')
        entry = position.get('entry_price', 0)
        if pos_count:
            report_lines.append(f"📍 *POSIÇÕES ABERTAS:* {pos_count} | Principal: {pos_symbol}")
        else:
            report_lines.append(f"📍 *POSIÇÃO ABERTA:* {pos_symbol}")
        report_lines.append(f"   Entrada: ${entry:.2f}")
        report_lines.append("")
    else:
        report_lines.append("📍 *Sem posição aberta*")
        report_lines.append("")
    
    # Análise de cada moeda
    report_lines.append("*ANÁLISE DAS MOEDAS:*")
    report_lines.append("")
    
    opportunities = []
    close_opportunities = []
    
    market_cache = snap.get('market_overview', {}) or {}

    for symbol in WATCHLIST:
        try:
            data = market_cache.get(symbol)
            if not data:
                continue

            price = data.get('price')
            rsi = data.get('rsi')
            bb_lower = data.get('bb_lower')
            bb_upper = data.get('bb_upper')

            if price is not None and rsi is not None and bb_lower is not None:
                tolerance = bb_lower * SANDRA["ENTRY_TOL"]
                buy_limit = bb_lower + tolerance
                
                # Calcula distância do preço para a zona de compra
                dist_to_buy = ((price - buy_limit) / buy_limit) * 100
                
                # Determina emoji e status
                entry_rsi = SANDRA["ENTRY_RSI"]
                if rsi < entry_rsi and price <= buy_limit:
                    emoji = "🟢"
                    status = "COMPRA!"
                    opportunities.append(symbol)
                elif rsi < (entry_rsi + 5) or dist_to_buy < 2:
                    emoji = "🟡"
                    status = "QUASE"
                    close_opportunities.append((symbol, rsi, dist_to_buy))
                elif rsi > 70:
                    emoji = "🔴"
                    status = "RISCO"
                else:
                    emoji = "⚪"
                    status = "AGUARD"
                
                # Linha do relatório
                coin_name = symbol.replace('/USDT', '')
                report_lines.append(f"{emoji} *{coin_name}*: RSI={rsi:.0f} | ${price:.2f}")
                report_lines.append(f"   └ Limite compra: ${buy_limit:.2f} ({dist_to_buy:+.1f}%)")
        except Exception as e:
            print(f"Erro ao analisar {symbol}: {e}")
    
    report_lines.append("")
    
    # PnL do dia e total (Sandra Mode: dinheiro líquido)
    day_net = snap.get('pnl', {}).get('day_net', 0.0)
    total_net = snap.get('pnl', {}).get('total_net', 0.0)
    report_lines.append(f"💰 *PnL Hoje (líquido):* ${day_net:+.2f} | *Acúmulo:* ${total_net:+.2f}")
    report_lines.append("")
    
    # Resumo
    if opportunities:
        report_lines.append(f"🚨 *OPORTUNIDADES AGORA:* {', '.join(opportunities)}")
    elif close_opportunities:
        report_lines.append("⚠️ *MOEDAS PRÓXIMAS DE COMPRA:*")
        for sym, rsi, dist in close_opportunities:
            coin = sym.replace('/USDT', '')
            report_lines.append(f"   • {coin}: RSI={rsi:.0f}, falta {abs(dist):.1f}% p/ banda")
    else:
        report_lines.append("😴 *Nenhuma oportunidade no momento*")
        report_lines.append("   Aguardando RSI < 35 + preço na banda inferior")
    
    return "\n".join(report_lines)


def send_daily_report():
    """Envia relatório diário via Telegram."""
    try:
        report = generate_market_report()
        send_telegram_message(report)
        print(f"📨 Relatório enviado às {now_sp().strftime('%H:%M')}")
        logging.info("Relatório diário enviado via Telegram")
    except Exception as e:
        print(f"❌ Erro ao enviar relatório: {e}")
        logging.error(f"Erro ao enviar relatório: {e}")


def check_and_send_reports():
    """Verifica se está na hora de enviar relatório."""
    global last_report_hour
    current_hour = now_sp().hour
    
    # Só envia se mudou de hora e está em um dos horários programados
    if current_hour in REPORT_HOURS and current_hour != last_report_hour:
        last_report_hour = current_hour
        send_daily_report()


# ==================== RELATÓRIO DIÁRIO (E-MAIL) ====================

_last_email_report_date = None


def maybe_send_daily_email_report() -> None:
    """Envia fechamento diário via E-mail (Gmail SMTP) e também no Telegram.

    - Controlado por EMAIL_ENABLED.
    - Envia 1x por dia após o horário alvo (padrão 23:59 SP).
    - Nunca loga senha; falhas não derrubam o loop.
    """
    global _last_email_report_date

    if not build_daily_summary or not format_daily_summary_text or not send_email_smtp:
        return

    enabled = str(os.getenv('EMAIL_ENABLED', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
    if not enabled:
        return

    now = now_sp()
    date_str = now.strftime('%Y-%m-%d')

    # Horário configurável (padrão 23:59)
    try:
        hour = int(os.getenv('DAILY_EMAIL_REPORT_HOUR', '23') or 23)
        minute = int(os.getenv('DAILY_EMAIL_REPORT_MINUTE', '59') or 59)
    except Exception:
        hour, minute = 23, 59

    if (now.hour, now.minute) < (hour, minute):
        return

    if _last_email_report_date == date_str:
        return

    try:
        summary = build_daily_summary(DB_FILE, date_str=date_str, days_rolling=7)
        body = format_daily_summary_text(summary)
        subject = f"Fechamento Sandra ({date_str})"

        ok = send_email_smtp(subject=subject, body=body)
        if ok:
            _last_email_report_date = date_str
            try:
                send_telegram_message(body)
            except Exception:
                pass
            print(f"📧 Fechamento diário enviado por e-mail ({date_str})")
        else:
            print("⚠️ EMAIL_ENABLED está ligado, mas envio SMTP falhou (ver variáveis no .env).")
    except Exception as e:
        print(f"❌ Erro ao gerar/enviar fechamento diário por e-mail: {e}")


def send_daily_email_report_now() -> tuple[bool, str]:
    """Dispara o relatório diário imediatamente (para teste manual).

    Retorna (ok, mensagem). Respeita EMAIL_ENABLED e configuração SMTP.
    """
    global _last_email_report_date

    if not build_daily_summary or not format_daily_summary_text or not send_email_smtp:
        return False, "Módulo de e-mail indisponível"

    enabled = str(os.getenv('EMAIL_ENABLED', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
    if not enabled:
        return False, "EMAIL_ENABLED está desligado. Configure no .env (EMAIL_ENABLED=true + SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS + EMAIL_TO) e reinicie o serviço systemd."

    now = now_sp()
    date_str = now.strftime('%Y-%m-%d')

    try:
        summary = build_daily_summary(DB_FILE, date_str=date_str, days_rolling=7)
        body = format_daily_summary_text(summary)
        subject = f"Fechamento Sandra ({date_str}) [TESTE]"

        ok = send_email_smtp(subject=subject, body=body)
        if not ok:
            return False, "Falha no envio SMTP (ver SMTP_* no .env)"

        # Marca como enviado hoje para evitar duplicar acidentalmente
        _last_email_report_date = date_str

        try:
            send_telegram_message(body)
        except Exception:
            pass

        return True, "Relatório enviado (e-mail + Telegram)"
    except Exception as e:
        return False, f"Erro: {e}"


# ==================== FIM SISTEMA DE RELATÓRIOS ====================

# Controle para não spammar alertas
_last_opportunity_alert = {}

def send_opportunity_alert(symbol, price, rsi, bb_lower, scalper_ok=None, scalper_reason=None):
    """Envia alerta de oportunidade (radar). Compra final depende do Scalper Blindado + travas."""
    global _last_opportunity_alert
    
    # Evita spam: só alerta a cada 5 minutos por moeda
    current_time = time.time()
    last_alert = _last_opportunity_alert.get(symbol, 0)
    if current_time - last_alert < 300:  # 5 minutos
        return
    
    _last_opportunity_alert[symbol] = current_time
    
    # Calcula distância para a banda
    dist_to_band = ((price - bb_lower) / bb_lower) * 100
    
    # Determina o nível de proximidade (radar)
    entry_rsi = SANDRA["ENTRY_RSI"]
    if rsi < entry_rsi and dist_to_band <= 1:
        status = "🟢 Radar forte (condições básicas ok)"
    elif rsi < entry_rsi:
        status = f"🟡 RSI OK (precisa <{entry_rsi}), preço {dist_to_band:.1f}% acima da banda"
    elif dist_to_band <= 1:
        status = f"🟡 Preço OK, RSI={rsi:.1f} (precisa <{entry_rsi})"
    else:
        status = f"⏳ Quase... RSI={rsi:.1f} | {dist_to_band:.1f}% da banda"

    scalper_txt = ""
    if scalper_ok is True:
        scalper_txt = f"\n\n✅ *Scalper Blindado:* APROVOU\n_{scalper_reason or 'sem detalhe'}_"
    elif scalper_ok is False:
        scalper_txt = f"\n\n⛔ *Scalper Blindado:* BLOQUEOU\n_{scalper_reason or 'sem detalhe'}_"

    note = (
        "\n\nℹ️ *Obs:* Este alerta é um *radar*. A compra automática só acontece se o"
        " Scalper aprovar *e* não houver travas (cooldown, proteção BTC, mínimo do par, saldo, etc.)."
    )
    
    msg = (
        f"👀 *OPORTUNIDADE DETECTADA*\n\n"
        f"🪙 {symbol}\n"
        f"💵 Preço: ${price:.4f}\n"
        f"📊 RSI: {rsi:.1f}\n"
        f"📉 Banda Inferior: ${bb_lower:.4f}\n"
        f"📏 Distância: {dist_to_band:.1f}%\n\n"
        f"{status}"
        f"{scalper_txt}"
        f"{note}"
    )
    
    print(f"👀 Oportunidade: {symbol} | RSI={rsi:.1f} | Dist={dist_to_band:.1f}%")
    send_telegram_message(msg)


def analyze_market_with_gpt(symbol, price, rsi, bb_lower, action_type):
    """IA que analisa histórico e ajusta estratégia automaticamente."""
    client = get_openai_client()
    if not client:
        return "🤖 IA não configurada."

    # Coleta histórico de trades para análise
    selected = lab_state['selected_strategy']
    trades = lab_state['strategies'][selected].get('trades', [])
    
    # Analisa últimos 5 trades
    ultimos_trades = trades[-5:] if len(trades) >= 5 else trades
    trades_perdidos = [t for t in ultimos_trades if t.get('profit_pct', 0) < -2]
    trades_ganhos = [t for t in ultimos_trades if t.get('profit_pct', 0) > 0]
    
    # Calcula RSI médio das operações
    rsi_medio = sum([t.get('rsi', 35) for t in ultimos_trades]) / len(ultimos_trades) if ultimos_trades else 35
    
    # Contexto do mercado atual
    market_context = f"RSI atual={rsi:.1f}, preço=${price:.2f}, banda=${bb_lower:.2f}"
    
    # Parâmetros atuais (Sandra Mode real)
    params_atuais = f"ENTRY_RSI={SANDRA['ENTRY_RSI']}, TOL={SANDRA['ENTRY_TOL']}, STOP_BASE={SANDRA['STOP_BASE']}%"
    
    prompt = f"""Você é chefe de estratégia agora, olha o último ciclo:
- Últimos 5 trades: {len(trades_perdidos)} perdidos acima de 2%, {len(trades_ganhos)} ganhos, RSI médio foi {rsi_medio:.1f}.
- Mercado: {market_context}
- Parâmetros atuais: {params_atuais}

Regras:
- Se perdeu 2 ou mais seguidos: diminui RSI pra 32, reduz tolerância pra 0.5%, stop loss pra -2.5%.
- Se ganhou fácil em RSI <35: mantém tudo, só diz 'segura firme'.
- Se RSI >70 por 3 dias: vira conservadora — RSI 38, venda no primeiro 2%.

Responde EXATAMENTE assim (duas linhas):
Ação: ajuste ou mantém
Telegram: uma frase curta tipo 'IA mudou o plano — agora mais esperta'

Nada de enrolação."""

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SANDRA_PROMPT},
                {"role": "system", "content": "Responda APENAS no formato pedido. Não invente dados. Se faltar informação, seja conservador."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0  # Sandra: determinístico
        )
        
        content = response.choices[0].message.content.strip()
        res = content.split('\n')
        
        # Parse da resposta
        acao = ""
        telegram_msg = ""
        
        for line in res:
            if line.lower().startswith('ação:') or line.lower().startswith('acao:'):
                acao = line.split(':', 1)[1].strip() if ':' in line else ''
            elif line.lower().startswith('telegram:'):
                telegram_msg = line.split(':', 1)[1].strip() if ':' in line else ''
        
        # Aplica ajustes se necessário
        if 'ajuste' in acao.lower() or 'ajustar' in acao.lower():
            with state_lock:
                SANDRA["ENTRY_RSI"] = 32
                SANDRA["ENTRY_TOL"] = 0.005
                SANDRA["STOP_BASE"] = -2.5
                lab_state.setdefault('streak', {'wins': 0, 'losses': 0, 'tight': False})
                lab_state['streak']['tight'] = True
            
            print(f"🤖 IA AJUSTOU SANDRA: ENTRY_RSI={SANDRA['ENTRY_RSI']}, TOL={SANDRA['ENTRY_TOL']}, STOP_BASE={SANDRA['STOP_BASE']}%")
            send_telegram_message(
                f"🤖 IA ajustou a Sandra\\n\\n{telegram_msg}\\n\\n"
                f"Novos params: RSI<{SANDRA['ENTRY_RSI']}, Tol {SANDRA['ENTRY_TOL']*100:.1f}%, Stop {SANDRA['STOP_BASE']}%"
            )
        else:
            if telegram_msg:
                send_telegram_message(f"🟢 {telegram_msg}")
        
        return content
        
    except Exception as e:
        print(f"❌ Erro GPT: {e}")
        return "🤖 Erro na análise de IA."

# ---------------------------------


# === PRIORIDADE SANDRA: ADA, DOGE, XRP, LINK primeiro; BTC/ETH só se tudo ruim ===
# PEPE e WIF trazem volatilidade. DOGE e SOL trazem liquidez.
PRIORITY_COINS = ['PEPE/USDT', 'WIF/USDT', 'DOGE/USDT', 'SOL/USDT']
SECONDARY_COINS = ['DOT/USDT', 'LTC/USDT', 'ADA/USDT', 'BNB/USDT']
LAST_RESORT = ['ETH/USDT', 'BTC/USDT']  # só se tudo mais estiver ruim

WATCHLIST = PRIORITY_COINS + SECONDARY_COINS + LAST_RESORT


def juiz_de_moedas(symbol: str, coin_id: str, *, coin_name: str = "") -> tuple[bool, str, str]:
    """IA que julga fundamentos básicos via CoinGecko antes de entrar no radar.

    Retorna: (aprovado, motivo, risco)
    """
    if os.getenv('ENABLE_JUIZ', 'true').lower() != 'true':
        return True, 'Juiz desativado (ENABLE_JUIZ=false)', 'Medio'

    symbol = (symbol or '').upper().strip()
    coin_id = (coin_id or '').strip()
    if not symbol or not coin_id:
        return True, 'Sem coin_id (fallback)', 'Medio'

    # Regras duras (evita depender só de IA)
    privacy_blacklist = {'XMR', 'ZEC', 'DASH'}
    if symbol in privacy_blacklist:
        return False, f"Rejeitado: Privacy Coin ({symbol})", 'Alto'

    # Cache
    try:
        ttl_s = int(os.getenv('JUIZ_CACHE_TTL_S', str(7 * 24 * 60 * 60)))  # 7 dias
    except Exception:
        ttl_s = 7 * 24 * 60 * 60

    now_ts = time.time()
    with state_lock:
        cache = lab_state.setdefault('judge_cache', {})
        cached = cache.get(coin_id)
    if isinstance(cached, dict):
        ts = float(cached.get('ts', 0) or 0)
        if now_ts - ts <= ttl_s:
            return bool(cached.get('approved', False)), str(cached.get('reason') or ''), str(cached.get('risk') or 'Medio')

    print(f"⚖️ JUIZ: Analisando fundamentos de {symbol} ({coin_id})...")

    # 1) Dossiê CoinGecko
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "projetobinace/1.0"},
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"CoinGecko HTTP {resp.status_code}")
        data = resp.json() or {}
    except Exception as e:
        # Fallback conservador: se não conseguir checar, não bloqueia a caça inteira
        approved, reason, risk = True, f"Juiz indisponível ({e})", 'Medio'
        with state_lock:
            lab_state.setdefault('judge_cache', {})[coin_id] = {
                'ts': now_ts,
                'approved': approved,
                'reason': reason,
                'risk': risk,
            }
        return approved, reason, risk

    description = ((data.get('description', {}) or {}).get('en') or '').strip()
    categories = data.get('categories') or []
    if not isinstance(categories, list):
        categories = []
    categories_txt = ", ".join([str(c) for c in categories if c])
    homepage = "N/A"
    try:
        homepage = ((data.get('links', {}) or {}).get('homepage') or ['N/A'])[0] or 'N/A'
    except Exception:
        homepage = 'N/A'
    try:
        rank = int(data.get('market_cap_rank') or 999999)
    except Exception:
        rank = 999999

    if len(description) < 50:
        approved, reason, risk = False, 'Sem descrição suficiente (suspeito)', 'Alto'
        with state_lock:
            lab_state.setdefault('judge_cache', {})[coin_id] = {
                'ts': now_ts,
                'approved': approved,
                'reason': reason,
                'risk': risk,
            }
        return approved, reason, risk

    # 2) Consulta GPT (Auditor)
    client = get_openai_client()
    if not client:
        # fallback mais seguro do que "aprova tudo": deixa passar só se rank for bom
        approved = bool(rank <= 200)
        reason = 'Sem IA: aprovado por rank' if approved else 'Sem IA: rank alto'
        risk = 'Medio' if approved else 'Alto'
        with state_lock:
            lab_state.setdefault('judge_cache', {})[coin_id] = {
                'ts': now_ts,
                'approved': approved,
                'reason': reason,
                'risk': risk,
            }
        return approved, reason, risk

    prompt = f"""
Você é um Auditor Sênior de Criptomoedas. Analise este projeto para investimento de curto prazo (scalping).\n\n
NOME/SÍMBOLO: {symbol}\n
PROJETO: {coin_name or 'N/A'}\n
RANK (market cap): {rank}\n
CATEGORIAS: {categories_txt or 'N/A'}\n
SITE: {homepage}\n
DESCRIÇÃO (resumo): {description[:800]}\n\n
REGRAS DE APROVAÇÃO:\n
1) REJEITE se parecer rug pull/golpe/projeto abandonado.\n
2) REJEITE se for Privacy Coin com risco de delisting (XMR/ZEC/DASH etc.).\n
3) APROVE se parecer legítimo e com liquidez (projeto consolidado OU meme gigante).\n
4) Seja conservador: na dúvida, rejeite.\n\n
Responda APENAS no formato JSON:\n
{{\n  \"aprovado\": true/false,\n  \"motivo\": \"Uma frase curta\",\n  \"risco\": \"Baixo/Medio/Alto\"\n}}\n
""".strip()

    try:
        # tenta JSON estrito (se o SDK suportar)
        try:
            resp = client.chat.completions.create(
                model=os.getenv('JUIZ_MODEL', OPENAI_MODEL),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=250,
                response_format={"type": "json_object"},
            )
        except TypeError:
            resp = client.chat.completions.create(
                model=os.getenv('JUIZ_MODEL', OPENAI_MODEL),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=250,
            )

        raw = (resp.choices[0].message.content or '').strip()
        try:
            parsed = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.S)
            parsed = json.loads(m.group(0)) if m else {}

        approved = bool(parsed.get('aprovado', False))
        reason = str(parsed.get('motivo') or 'Sem motivo')
        risk = str(parsed.get('risco') or 'Alto')

    except Exception as e:
        approved, reason, risk = (rank <= 200), f"Falha GPT: {e}", ('Medio' if rank <= 200 else 'Alto')

    with state_lock:
        lab_state.setdefault('judge_cache', {})[coin_id] = {
            'ts': now_ts,
            'approved': approved,
            'reason': reason,
            'risk': risk,
        }

    return approved, reason, risk


def cacador_de_gemas():
    """MÓDULO OLHEIRO: busca moedas em destaque na CoinGecko e adiciona ao radar se existir na Binance.

    Segurança:
    - Só adiciona pares `*/USDT` que passam no teste de ticker público.
    - Filtra por `market_cap_rank` (configurável).
    - Limita quantas moedas entram por varredura.

    Isso NÃO compra no topo; apenas coloca na WATCHLIST para ser monitorada e
    passar pelos gates normais (RSI, etc.).
    """
    if os.getenv('ENABLE_CACADOR', 'true').lower() != 'true':
        return []

    try:
        max_rank = int(os.getenv('CACADOR_MAX_RANK', '1000'))
    except Exception:
        max_rank = 1000

    try:
        max_new = int(os.getenv('CACADOR_MAX_NEW', '5'))
    except Exception:
        max_new = 5

    print("🔭 CAÇADOR: Varrendo CoinGecko (trending) em busca de gemas...")
    novas: list[str] = []

    try:
        url = "https://api.coingecko.com/api/v3/search/trending"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "projetobinace/1.0"})
        if resp.status_code != 200:
            print(f"🔭 CAÇADOR: CoinGecko HTTP {resp.status_code}.")
            return []

        data = resp.json() or {}
        coins = data.get('coins') or []
        if not coins:
            print("🔭 CAÇADOR: Sem resultados na CoinGecko agora.")
            return []

        try:
            max_judge = int(os.getenv('CACADOR_MAX_JUDGE', '3'))
        except Exception:
            max_judge = 3
        judged = 0

        for item in coins:
            if len(novas) >= max_new:
                break

            coin_item = (item or {}).get('item') or {}
            symbol = str(coin_item.get('symbol') or '').upper().strip()
            name = str(coin_item.get('name') or '').strip()
            coin_id = str(coin_item.get('id') or '').strip()
            market_cap_rank = coin_item.get('market_cap_rank')
            try:
                market_cap_rank = int(market_cap_rank) if market_cap_rank is not None else 999999
            except Exception:
                market_cap_rank = 999999

            if not symbol or '/' in symbol:
                continue
            if market_cap_rank > max_rank:
                continue

            binance_symbol = f"{symbol}/USDT"

            with state_lock:
                if binance_symbol in WATCHLIST:
                    continue

            # Verifica se existe na Binance (ticker público)
            try:
                if not public_exchange:
                    continue
                t = ex(public_exchange.fetch_ticker, binance_symbol)
                last_price = t.get('last')
                if last_price is None:
                    continue

                # Juiz (IA) antes de adicionar
                if os.getenv('ENABLE_JUIZ', 'true').lower() == 'true' and coin_id:
                    if judged >= max_judge:
                        continue
                    judged += 1
                    ok, reason, risk = juiz_de_moedas(symbol, coin_id, coin_name=name)
                    if not ok:
                        print(f"⛔ JUIZ REJEITOU {binance_symbol}: {reason} (Risco: {risk})")
                        continue

                with state_lock:
                    lab_state.setdefault('dynamic_watchlist', [])
                    if binance_symbol not in lab_state['dynamic_watchlist']:
                        # Cap simples para não crescer sem limite
                        if len(lab_state['dynamic_watchlist']) < 50:
                            lab_state['dynamic_watchlist'].append(binance_symbol)
                    if binance_symbol not in WATCHLIST:
                        WATCHLIST.append(binance_symbol)

                    if binance_symbol not in HIGH_VOLATILITY_COINS:
                        HIGH_VOLATILITY_COINS.append(binance_symbol)

                novas.append(f"{binance_symbol} (${float(last_price):.6f}) — {name} (rank {market_cap_rank})")
            except Exception:
                continue

        if novas:
            msg = "🚀 *CAÇADOR: NOVAS MOEDAS NO RADAR*\n\n" + "\n".join([f"- {x}" for x in novas])
            send_telegram_message(msg)
            print(f"✅ CAÇADOR: adicionadas {len(novas)} moedas.")
        else:
            print("🔭 CAÇADOR: Nenhuma gema nova na Binance agora.")

        return novas

    except Exception as e:
        print(f"⚠️ Erro no CAÇADOR: {e}")
        return []

# === MODO SANDRA: APOSTAS VARIÁVEIS ===
HIGH_VOLATILITY_COINS = ['DOGE/USDT', 'ADA/USDT', 'SOL/USDT', 'XRP/USDT', 'LINK/USDT']
GLOBAL_STATS = {'peak_balance': 0.0, 'drawdown_mode': False}

# Valor mínimo de ordem na Binance (em USDT) - 8.0 para permitir proteção $8
MIN_ORDER_VALUE = 8.0


def get_min_notional_usdt(symbol: str, fallback: float = 10.0) -> float:
    """Retorna min notional (USDT) do par (Binance/CCXT).

    Observação: muitos pares exigem ~$10+; no modo proteção a Sandra NÃO deve
    "furar" aumentando aposta só para passar no mínimo.
    """
    try:
        if exchange:
            market = exchange.market(symbol)
            lim = (market.get('limits', {}) or {}).get('cost', {}) or {}
            m = lim.get('min', None)
            if m is not None:
                return float(m)

            info = market.get('info', {}) or {}
            filters = info.get('filters', []) or []
            for f in filters:
                if (f.get('filterType') or '').upper() in ('MIN_NOTIONAL', 'NOTIONAL'):
                    v = f.get('minNotional') or f.get('notional') or f.get('minNotionalValue')
                    if v is not None:
                        return float(v)
    except Exception:
        pass
    return float(fallback)

# === CONFIG SANDRA MODE CENTRALIZADO ===
SANDRA = {
    "BASE_BET": 11.0,
    "BET_STRONG": 22.0,
    "BET_GOLD": 33.0,
    "BET_DRAWDOWN": 8.0,
    "MAX_BET": 33.0,
    
    "ENTRY_RSI": 35,
    "ENTRY_TOL": 0.01,  # 1%
    "STRONG_RSI": 25,
    "GOLD_RSI": 20,
    "DRAWDOWN_RSI": 30,
    
    "SELL_RSI": 65,
    
    # 🧠 IA DINÂMICA: SL/TP são calculados por ATR + ADX + Sentimento
    "STOP_BASE": -3.0,  # Fallback (se IA falhar)
    "STOP_DRAWDOWN": -2.0,
    "TP_SLOW": 5.0,  # Fallback (se IA falhar)
    
    # Valores dinâmicos calculados pela IA (atualizados por posição)
    "STOP_DINAMICO": -1.8,  # Calculado por calcular_sl_dinamico()
    "TP_DINAMICO": 4.0,  # Calculado por calcular_tp_dinamico()
    "USE_DYNAMIC_RISK": True,  # Flag para ativar/desativar IA dinâmica
    
    "FAST_PROFIT": 8.0,
    "FAST_WINDOW_S": 300,
    "TRAIL_FAST": 3.0,

    # Tempo máximo segurando posição (segundos). 24h por padrão.
    "MAX_HOLD_S": 24 * 60 * 60,

    # Após estourar o tempo máximo, regras de reavaliação:
    # - Se houver lucro mínimo, realiza para liberar capital.
    # - Se estiver com prejuízo acima do corte, encerra para limitar dano.
    "MAX_HOLD_TAKE_PROFIT_PCT": 0.30,
    "MAX_HOLD_CUT_LOSS_PCT": -2.50,
}

# Cache BTC (evita spam de API)
BTC_CACHE = {
    "dump15": {"ts": 0, "val": False},
    "bleed3d": {"ts": 0, "val": False},
}
btc_cache_lock = threading.RLock()

_market_cache_lock = threading.RLock()
_market_cache: dict[str, dict] = {}
MARKET_CACHE_TTL_S = 10


def btc_drop_15m():
    """Detecta se BTC caiu >2% nos últimos 15 minutos (3 candles de 5m)."""
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': 'BTCUSDT', 'interval': '5m', 'limit': 5}
        raw = _http_get_json(url, params=params, timeout=10, retries=2)
        close_now = float(raw[-1][4])
        close_15m = float(raw[-4][4])  # 3 candles atrás
        drop = (close_now - close_15m) / close_15m * 100
        return drop <= -2.0
    except Exception as e:
        print(f"⚠️ Erro ao verificar BTC -2%/15min: {e}")
        return False


def btc_bleeding_3days():
    """Detecta se BTC está sangrando (3 dias vermelhos consecutivos no diário)."""
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': 'BTCUSDT', 'interval': '1d', 'limit': 4}
        raw = _http_get_json(url, params=params, timeout=10, retries=2)
        
        # Verifica os últimos 3 dias fechados (ignora o dia atual)
        red_days = 0
        for candle in raw[-4:-1]:  # Últimos 3 dias (exclui hoje)
            open_price = float(candle[1])
            close_price = float(candle[4])
            if close_price < open_price:  # Dia vermelho
                red_days += 1
        
        return red_days >= 3
    except Exception as e:
        print(f"⚠️ Erro ao verificar BTC 3 dias sangrar: {e}")
        return False


def btc_drop_15m_cached(ttl=20):
    """Cache de btc_drop_15m para evitar spam de API (TTL 20s)."""
    now = time.time()
    with btc_cache_lock:
        ts = BTC_CACHE["dump15"]["ts"]
        val = BTC_CACHE["dump15"]["val"]
    if now - ts <= ttl:
        return val

    new_val = btc_drop_15m()
    with btc_cache_lock:
        BTC_CACHE["dump15"]["ts"] = now
        BTC_CACHE["dump15"]["val"] = new_val
    return new_val


def btc_bleeding_3days_cached(ttl=3600):
    """Cache de btc_bleeding_3days (TTL 1h - diário não muda rápido)."""
    now = time.time()
    with btc_cache_lock:
        ts = BTC_CACHE["bleed3d"]["ts"]
        val = BTC_CACHE["bleed3d"]["val"]
    if now - ts <= ttl:
        return val

    new_val = btc_bleeding_3days()
    with btc_cache_lock:
        BTC_CACHE["bleed3d"]["ts"] = now
        BTC_CACHE["bleed3d"]["val"] = new_val
    return new_val


def fetch_raw_candles(symbol, interval='5m', limit=100):
    """Busca dados brutos para o Pandas processar (ccxt ou requests)."""
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': symbol.replace('/', ''), 'interval': interval, 'limit': limit}
        # Retorna apenas as colunas essenciais
        raw_data = _http_get_json(url, params=params, timeout=10, retries=2)
        # Filtra apenas o necessário: time, open, high, low, close, volume
        clean_data = [x[:6] for x in raw_data] 
        return clean_data
    except Exception as e:
        print(f"❌ Erro ao buscar dados raw ({symbol}): {e}")
        return []

def fetch_market_data(symbol, interval='5m', limit=60):
    """Busca dados de mercado no timeframe de sinal (5m) + volume."""
    cache_key = f"{symbol}:{interval}:{limit}"
    now_mono = time.monotonic()
    with _market_cache_lock:
        entry = _market_cache.get(cache_key)
        if entry and (now_mono - entry['ts']) <= MARKET_CACHE_TTL_S:
            return entry['value']
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': symbol.replace('/', ''), 'interval': interval, 'limit': limit}
        raw_data = _http_get_json(url, params=params, timeout=10, retries=2)
        
        closes = [float(candle[4]) for candle in raw_data]
        volumes = [float(candle[5]) for candle in raw_data]
        
        current_price = closes[-1]
        rsi = calculate_rsi(closes)
        upper, sma, lower = calculate_bollinger(closes)
        
        vol_now = volumes[-1]
        vol_avg = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(np.mean(volumes))
        
        value = (current_price, rsi, lower, upper, vol_now, vol_avg)
        with _market_cache_lock:
            _market_cache[cache_key] = {'ts': now_mono, 'value': value}
        return value
    except Exception as e:
        print(f"❌ Erro ao buscar dados ({symbol}): {e}")
        with _market_cache_lock:
            entry = _market_cache.get(cache_key)
            if entry:
                return entry['value']
        return None, None, None, None, None, None


def check_strategy_signal(strategy_name, price, rsi, bb_lower, symbol, vol_now, vol_avg, btc_is_dumping_15m, btc_bleeding):
    """
    CÉREBRO SANDRA MODE com config centralizado.
    """
    # 0. Mercado sangrar 3 dias: PARA DE COMPRAR
    if btc_bleeding:
        print(f"🩸 MERCADO SANGRANDO 3 DIAS - Não compra até voltar")
        return 0.0
    
    # 1. Modo Proteção (drawdown 10%)
    with state_lock:
        drawdown_mode = bool(GLOBAL_STATS.get('drawdown_mode', False))

    if drawdown_mode:
        if rsi < SANDRA["DRAWDOWN_RSI"] and price <= bb_lower * (1 + SANDRA["ENTRY_TOL"]):
            return SANDRA["BET_DRAWDOWN"]
        return 0.0

    # 2. Regra base de entrada
    base_entry = (rsi < SANDRA["ENTRY_RSI"]) and (price <= bb_lower * (1 + SANDRA["ENTRY_TOL"]))
    
    if not base_entry:
        return 0.0
    
    # 3. $33: RSI <20 e BTC cai >2% em 15 min
    if rsi < SANDRA["GOLD_RSI"] and btc_is_dumping_15m:
        print(f"💎 SINAL EXCEPCIONAL em {symbol}! RSI={rsi:.1f} + BTC despencando (Apostando ${SANDRA['BET_GOLD']})")
        return SANDRA["BET_GOLD"]
    
    # 4. $22: RSI <25 e volume >20% acima da média
    if rsi < SANDRA["STRONG_RSI"] and vol_avg and (vol_now > 1.2 * vol_avg):
        print(f"🔥 SINAL FORTE em {symbol}. RSI={rsi:.1f} + Volume alto (Apostando ${SANDRA['BET_STRONG']})")
        return SANDRA["BET_STRONG"]
    
    # 5. $11: Padrão
    return SANDRA["BASE_BET"]


def update_sandra_streak(net_profit_usdt):
    """Ajusta Sandra baseado em streak (2 perdas = aperta, 2 wins = volta)."""
    tighten = False
    relax = False
    with state_lock:
        st = lab_state.setdefault("streak", {"wins": 0, "losses": 0, "tight": False})

        if net_profit_usdt < 0:
            st["losses"] += 1
            st["wins"] = 0
        else:
            st["wins"] += 1
            st["losses"] = 0

        # 2 perdas seguidas => aperta tudo
        if st["losses"] >= 2 and not st["tight"]:
            st["tight"] = True
            SANDRA["ENTRY_RSI"] = 32
            SANDRA["STOP_BASE"] = -2.5
            SANDRA["ENTRY_TOL"] = 0.005
            tighten = True

        # 4 wins seguidas => solta pro padrão
        if st["tight"] and st["wins"] >= 4:
            st["tight"] = False
            SANDRA["ENTRY_RSI"] = 35
            SANDRA["STOP_BASE"] = -3.0
            SANDRA["ENTRY_TOL"] = 0.01
            relax = True

    if tighten:
        send_telegram_message("⚠️ Sandra apertou: 2 losses seguidas. Agora RSI<32 e stop mais curto.")
        return
    if relax:
        send_telegram_message("🟢 Sandra relaxou: 4 wins seguidas. Voltou ao padrão.")


def get_diagnostic(strategy_name, price, rsi, bb_lower, position=None):
    """Gera diagnóstico legível explicando por que não está comprando/vendendo."""
    
    # Se tem posição aberta, calcula lucro
    if position:
        entry_price = position.get('entry_price', price)
        profit_pct = ((price - entry_price) / entry_price) * 100
        emoji = "📈" if profit_pct > 0 else "📉"
        return f"{emoji} COMPRADO (Lucro: {profit_pct:+.2f}%)"
    
    # Verifica saldo primeiro
    with state_lock:
        usdt_balance = lab_state.get('real_balance', 0.0)
    if usdt_balance < MIN_ORDER_VALUE:
        return f"💸 SALDO BAIXO (${usdt_balance:.2f} < ${MIN_ORDER_VALUE})"
    
    # Analisa condições de compra (ESTRATÉGIA EQUILIBRADA)
    issues = []
    with state_lock:
        if bool(GLOBAL_STATS.get('drawdown_mode', False)):
            issues.append("🛡️ Proteção ativa (drawdown 10%)")
    rsi_target = SANDRA["ENTRY_RSI"]
    tolerance = bb_lower * SANDRA["ENTRY_TOL"]
    
    # Se RSI E preço estão bons, é sinal forte
    if rsi < rsi_target and price <= bb_lower + tolerance:
        return f"🚨 RSI < {rsi_target} + BANDA INFERIOR! COMPRA!"
    
    # RSI baixo mas preço não está na banda
    if rsi < rsi_target:
        diff_pct = ((price - bb_lower) / bb_lower) * 100
        return f"⚠️ RSI bom ({rsi:.1f}) mas preço {diff_pct:.1f}% acima da banda"
    
    if rsi >= rsi_target:
        issues.append(f"RSI={rsi:.1f} (precisa <35)")
    if price > bb_lower + tolerance:
        diff_pct = ((price - bb_lower) / bb_lower) * 100
        issues.append(f"Preço {diff_pct:.1f}% acima da banda")
    
    if not issues:
        return "🎯 PRONTO PARA COMPRAR!"
    
    return "⏳ " + " | ".join(issues)


def get_ai_context_data():
    """
    🧠 FUNÇÃO HELPER PARA IA (Telegram/OpenAI)
    
    Retorna um dicionário completo com TODOS os dados que a IA precisa consultar.
    Isso garante que a Sandra SEMPRE use valores dinâmicos (nunca fixos).
    
    Returns:
        dict: Contexto completo incluindo:
            - Sentimento do mercado (F&G Index)
            - SL/TP dinâmicos de todas as posições
            - Fator de juro composto
            - Saldo atual
            - Posições abertas com seus SL/TP
    """
    with state_lock:
        # 1. Sentimento do Mercado (Fear & Greed Index)
        market_sentiment = lab_state.get('market_sentiment', {})
        sentiment = market_sentiment.get('sentiment', 'DESCONHECIDO')
        fng_value = market_sentiment.get('fng_value', 50)
        
        # 2. Juro Composto
        compound_data = lab_state.get('compound_interest', {})
        fator_escala = compound_data.get('fator_escala', 1.0)
        saldo_atual = lab_state.get('real_balance', 0.0)
        
        # 3. Posições Abertas (com SL/TP dinâmicos)
        strategy_key = lab_state.get('selected_strategy', 'aggressive')
        strategy = lab_state['strategies'][strategy_key]
        positions = strategy.get('positions', {})
        
        # Formata posições com SL/TP
        positions_info = {}
        for symbol, pos in positions.items():
            sl_dinamico = pos.get('sl_dinamico')
            tp_dinamico = pos.get('tp_dinamico')
            
            # Se não tem dinâmico, usa fixo (mas indica que é fixo)
            if sl_dinamico is None:
                sl_usado = SANDRA.get('STOP_BASE', -3.0)
                sl_tipo = "FIXO"
            else:
                sl_usado = sl_dinamico
                sl_tipo = "DINÂMICO"
                
            if tp_dinamico is None:
                tp_usado = SANDRA.get('TP_SLOW', 5.0)
                tp_tipo = "FIXO"
            else:
                tp_usado = tp_dinamico
                tp_tipo = "DINÂMICO"
            
            positions_info[symbol] = {
                'entry_price': pos.get('entry_price'),
                'qty': pos.get('qty'),
                'entry_time': pos.get('entry_time'),
                'sl_pct': sl_usado,
                'sl_tipo': sl_tipo,
                'tp_pct': tp_usado,
                'tp_tipo': tp_tipo,
                'entry_rsi': pos.get('entry_rsi'),
            }
        
        # 4. Indicadores de Mercado (últimas leituras)
        market_overview = lab_state.get('market_overview', {})
        
        # Monta contexto completo
        context = {
            # Sentimento
            'sentimento': sentiment,
            'fear_greed_index': fng_value,
            'sentimento_descricao': (
                "PÂNICO (oportunidade de compra)" if sentiment == "BEAR" else
                "NEUTRO (mercado equilibrado)" if sentiment == "NEUTRO" else
                "GANÂNCIA (cuidado com topos)"
            ),
            
            # Juro Composto
            'fator_juro_composto': fator_escala,
            'saldo_atual': saldo_atual,
            'saldo_base': SALDO_BASE,
            'aposta_base_escalada': 11.0 * fator_escala,
            
            # Posições
            'posicoes_abertas': positions_info,
            'num_posicoes': len(positions_info),
            
            # Mercado
            'indicadores_por_moeda': market_overview,
            
            # Configuração Atual
            'sandra_config': {
                'ENTRY_RSI': SANDRA.get('ENTRY_RSI', 35),
                'STOP_BASE': SANDRA.get('STOP_BASE', -3.0),
                'TP_SLOW': SANDRA.get('TP_SLOW', 5.0),
                'USE_DYNAMIC_RISK': SANDRA.get('USE_DYNAMIC_RISK', False),
            }
        }
        
        return context


def check_exit_signal(position, current_price, rsi, bb_upper=None, strategy_name=None):
    """
    🧠 SAÍDA INTELIGENTE com IA DINÂMICA (ATR + ADX + Sentimento).
    """
    # Se for estratégia parcial, usa lógica específica
    if strategy_name == 'aggressive_parcial':
        return _check_exit_parcial(position, current_price, rsi, bb_upper)

    entry_price = float(position.get('entry_price', 0) or 0)

    # Sempre timezone-aware
    entry_time = parse_iso_dt(position.get('entry_time')) or now_sp()
    now = now_sp()

    if entry_price <= 0:
        return False, "Entry inválida"

    profit_pct = ((current_price - entry_price) / entry_price) * 100

    # 1) SAÍDA INTELIGENTE: RSI só vende se pagar taxas
    # Taxas totais típicas spot: 0.1% compra + 0.1% venda = 0.2%
    # Margem de segurança: 0.1% -> mínimo 0.3%
    try:
        LUCRO_MINIMO_TAXAS = float(os.getenv('LUCRO_MINIMO_TAXAS', '0.6'))
    except Exception:
        LUCRO_MINIMO_TAXAS = 0.6

    # Se RSI estiver MUITO alto, vende de qualquer jeito (proteção)
    if rsi is not None and rsi >= 78:
        return True, f"RSI Extremo ({rsi:.1f}) - Proteção de Crash"

    # RSI alto padrão: só vende se já tiver lucro suficiente
    if rsi is not None and rsi >= SANDRA["SELL_RSI"]:
        if profit_pct > LUCRO_MINIMO_TAXAS:
            return True, f"RSI Alto ({rsi:.1f}) + Lucro Garantido ({profit_pct:.2f}%)"
        # RSI alto mas sem margem: não vende por RSI, deixa outras regras decidirem
    
    # 2) 🧠 Stop loss DINÂMICO (IA ou fallback)
    with state_lock:
        drawdown_mode = bool(GLOBAL_STATS.get('drawdown_mode', False))
        use_dynamic = SANDRA.get("USE_DYNAMIC_RISK", False)
    
    # Se IA estiver ativa E a posição tiver SL personalizado, usa ele
    if use_dynamic and position.get('sl_dinamico') is not None:
        stop_limit = float(position['sl_dinamico'])
    else:
        # Fallback: modo antigo
        stop_limit = SANDRA["STOP_DRAWDOWN"] if drawdown_mode else SANDRA["STOP_BASE"]
    if profit_pct <= stop_limit:
        return True, f"STOP {stop_limit}%"

    # Se for mutar trailing/highest, isso deve acontecer sob state_lock
    # (o call-site do trading loop já garante isso)
    
    # 3) Ativa trailing se houve subida rápida (flag PERSISTENTE)
    elapsed = (now - entry_time).total_seconds()

    # Regra inteligente de tempo máximo: não vende cegamente.
    max_hold_s = float(SANDRA.get("MAX_HOLD_S", 0) or 0)
    hold_hint = ""
    if max_hold_s > 0 and elapsed >= max_hold_s:
        hours = max_hold_s / 3600.0
        hold_hint = f"Tempo>{hours:.0f}h"

        take_profit = float(SANDRA.get("MAX_HOLD_TAKE_PROFIT_PCT", 0.0) or 0.0)
        cut_loss = float(SANDRA.get("MAX_HOLD_CUT_LOSS_PCT", 0.0) or 0.0)

        # Se já tem um lucro mínimo após muito tempo, realiza.
        if take_profit > 0 and profit_pct >= take_profit:
            return True, f"{hold_hint} | realizar +{profit_pct:.2f}%"

        # Se já está em prejuízo relevante após muito tempo, corta.
        if cut_loss < 0 and profit_pct <= cut_loss:
            return True, f"{hold_hint} | cortar {profit_pct:.2f}%"

    if (not position.get("trail_active", False)) and (elapsed <= SANDRA["FAST_WINDOW_S"]) and (profit_pct >= SANDRA["FAST_PROFIT"]):
        position["trail_active"] = True
        print(f"🎢 Trailing ativado! Lucro {profit_pct:.1f}% em {elapsed:.0f}s")
    
    # Atualiza máxima
    highest = position.get("highest_price", entry_price)
    if current_price > highest:
        highest = current_price
        position["highest_price"] = highest
    
    # 3b) Trailing persistente (não desliga após 5min)
    if position.get("trail_active", False):
        pullback = ((highest - current_price) / highest) * 100
        if pullback >= SANDRA["TRAIL_FAST"]:
            return True, f"TRAIL {SANDRA['TRAIL_FAST']}% (subida rápida)"
        return False, f"{hold_hint + ' | ' if hold_hint else ''}Segurando (trailing ativo)"
    
    # 4) 🧠 TP DINÂMICO (IA ou fallback)
    with state_lock:
        use_dynamic = SANDRA.get("USE_DYNAMIC_RISK", False)
    
    if use_dynamic and position.get('tp_dinamico') is not None:
        tp_target = float(position['tp_dinamico'])
        if profit_pct >= tp_target:
            return True, f"🧠 TP DINÂMICO {tp_target:.1f}% (IA: ATR+ADX+Sentimento)"
    else:
        # Fallback: TP fixo (subida lenta)
        if profit_pct >= SANDRA["TP_SLOW"]:
            return True, f"TP {SANDRA['TP_SLOW']}% (subida lenta)"
    
    return False, f"{hold_hint + ' | ' if hold_hint else ''}Segurando"


def _check_exit_parcial(position, current_price, rsi, bb_upper):
    """Lógica de saída para estratégia aggressive_parcial (venda parcial progressiva)."""
    if not position:
        return False, "Sem posição"
    
    entry_price = float(position.get('entry_price', current_price))
    entry_qty = float(position.get('qty', 0))
    profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
    profit_usdt = (current_price - entry_price) * entry_qty
    
    # 1) STOP FIXO: -2%
    if profit_pct <= -2.0:
        return True, "STOP -2%"
    
    # 2) VENDA PARCIAL PROGRESSIVA: 25% a cada $1.50 de lucro
    sold_partial = position.get('sold_partial_slices', 0)
    target_slices = int(profit_usdt / 1.5)  # quantas fatias de $1.50 já atingiu
    
    if target_slices > sold_partial:
        # Marca que vendeu mais uma fatia
        position['sold_partial_slices'] = target_slices
        return True, f"PARCIAL ${profit_usdt:.2f} (fatia {target_slices})"
    
    # 3) RSI > 50 + banda superior: vende 50%
    if rsi > 50 and bb_upper and current_price >= bb_upper:
        if not position.get('sold_rsi50', False):
            position['sold_rsi50'] = True
            return True, "RSI>50 + Banda Superior (50%)"
    
    # 4) TP FINAL: +5% total (vende o resto)
    if profit_pct >= 5.0:
        return True, "TP +5%"
    
    return False, "Segurando (parcial)"


def convert_brl_to_usdt(min_brl=20):
    """Converte BRL para USDT automaticamente quando necessário."""
    try:
        balance = ex(exchange.fetch_balance)
        brl_balance = balance.get('free', {}).get('BRL', 0.0)
        usdt_balance = balance.get('free', {}).get('USDT', 0.0)
        
        # Se já tem USDT suficiente, não precisa converter
        if usdt_balance >= MIN_ORDER_VALUE:
            print(f"✅ Saldo USDT OK: ${usdt_balance:.2f}")
            return usdt_balance
        
        # Se não tem BRL suficiente para converter
        if brl_balance < min_brl:
            print(f"⚠️ Saldo BRL insuficiente para conversão: R${brl_balance:.2f} (mínimo R${min_brl})")
            return usdt_balance
        
        # Busca cotação USDT/BRL
        try:
            ticker = ex(exchange.fetch_ticker, 'USDT/BRL')
            usdt_price_brl = ticker['last']  # Preço de 1 USDT em BRL
            
            # Calcula quantidade de USDT a comprar (usando 95% do BRL para taxas)
            brl_to_use = brl_balance * 0.95
            usdt_qty = brl_to_use / usdt_price_brl
            
            print(f"🔄 Convertendo R${brl_to_use:.2f} para ~${usdt_qty:.2f} USDT...")
            
            # Executa ordem de compra de USDT com BRL
            order = ex(exchange.create_market_buy_order, 'USDT/BRL', usdt_qty)
            
            new_usdt = order['filled']
            total_usdt = usdt_balance + new_usdt
            print(f"✅ Conversão concluída! Recebido: ${new_usdt:.2f} USDT | Total: ${total_usdt:.2f}")
            
            # Notifica no Telegram
            msg = f"🔄 *CONVERSÃO BRL → USDT*\n\n💵 Convertido: R${brl_to_use:.2f}\n💰 Recebido: ${new_usdt:.2f} USDT\n📊 Saldo total: ${total_usdt:.2f} USDT"
            send_telegram_message(msg)
            
            # Atualiza saldo no estado
            with state_lock:
                lab_state['real_balance'] = total_usdt
                lab_state['brl_balance'] = brl_balance - brl_to_use
            
            return total_usdt
            
        except Exception as e:
            print(f"❌ Erro na conversão BRL->USDT: {e}")
            # Tenta par inverso BRL/USDT
            try:
                ticker = ex(exchange.fetch_ticker, 'BRL/USDT')
                # Vende BRL para obter USDT
                order = ex(exchange.create_market_sell_order, 'BRL/USDT', brl_balance * 0.95)
                new_usdt = order['cost']  # USDT recebido
                print(f"✅ Conversão alternativa concluída! Recebido: ${new_usdt:.2f} USDT")
                send_telegram_message(f"🔄 Conversão BRL→USDT: ${new_usdt:.2f}")
                with state_lock:
                    lab_state['real_balance'] = new_usdt
                return new_usdt
            except:
                return usdt_balance
            
    except Exception as e:
        print(f"❌ Erro ao verificar saldos para conversão: {e}")
        return 0.0


def generate_chart_image(symbol, timeframe='1m', limit=100):
    """Gera uma imagem de gráfico de velas (candlestick) em memória."""
    try:
        # Busca dados históricos (OHLCV)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv:
            return None

        # Cria DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)

        # Configura estilo do gráfico
        mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc)

        # Salva em buffer de memória
        buf = io.BytesIO()
        mpf.plot(df, type='candle', style=s, volume=True, savefig=dict(fname=buf, format='png', bbox_inches='tight'), title=f"{symbol} ({timeframe})")
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Erro ao gerar gráfico: {e}")
        return None

def send_chart_to_telegram(symbol, caption=""):
    """Gera e envia o gráfico para o Telegram."""
    try:
        chart_buf = generate_chart_image(symbol)
        if chart_buf:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
            files = {'photo': ('chart.png', chart_buf, 'image/png')}
            chat_ids = _get_telegram_chat_ids()
            if not chat_ids:
                print("⚠️ Telegram sem chat_id válido. Gráfico não enviado.")
                logging.warning("Telegram sem chat_id válido; gráfico não enviado.")
                return
            for chat_id in chat_ids:
                data = {'chat_id': chat_id, 'caption': caption}
                requests.post(url, data=data, files=files)
            print(f"Gráfico enviado para o Telegram: {symbol}")
        else:
            print("Falha ao gerar gráfico para envio.")
    except Exception as e:
        print(f"Erro ao enviar gráfico para Telegram: {e}")


def _gerar_justificativa_compra(symbol, rsi, buy_price, buy_qty, buy_total, taxa_est, 
                                 sl_usado, tp_usado, preco_sl, preco_tp, pos_info, reason=None):
    """
    🧠 JUSTIFICATIVA INTELIGENTE: Documenta por que a IA decidiu comprar.
    
    Fornece transparência total sobre:
    - Fonte dos dados (Binance API, Scalper Blindado, CEO Manager)
    - Análise técnica completa
    - Confluência de sinais
    - Tendência identificada
    - Risco/Recompensa calculado
    """
    try:
        # Identifica a classificação da moeda
        coin = symbol.split('/')[0].upper()
        from scalper_blindado import MOEDAS_FORTES
        tier = "👑 ELITE (Forte)" if coin in MOEDAS_FORTES else "🎰 ALTCOIN (Arriscada)"
        
        # Busca dados técnicos do market_overview
        market_data = lab_state.get('market_overview', {}).get(symbol, {})
        adx = market_data.get('adx', 0.0)
        atr = market_data.get('atr', 0.0)
        bb_lower = market_data.get('bb_lower', 0.0)
        vol_ratio = None
        
        # Calcula volume ratio se disponível
        try:
            last_decision = lab_state.get('last_decisions', {}).get(symbol, {})
            scalper_reason = last_decision.get('scalper_reason', 'Análise técnica favorável')
        except:
            scalper_reason = reason or 'Análise técnica favorável'
        
        # Busca sentimento de mercado
        try:
            sentiment, fng_value = ceo_manager.get_market_sentiment()
            sentimento_emoji = "😨" if sentiment == "BEAR" else "😐" if sentiment == "NEUTRO" else "😁"
            sentimento_texto = f"{sentimento_emoji} {sentiment} (F&G: {fng_value})"
        except:
            sentimento_texto = "😐 NEUTRO (dados indisponíveis)"
        
        # Análise de tendência baseada em ADX
        if adx > 40:
            tendencia = "📈 Tendência FORTE (ADX > 40) - Movimento sustentável"
        elif adx > 25:
            tendencia = "📊 Tendência MODERADA (ADX 25-40) - Confirmação presente"
        elif adx > 15:
            tendencia = "〰️ Tendência FRACA (ADX 15-25) - Mercado lateral"
        else:
            tendencia = "🔄 SEM TENDÊNCIA (ADX < 15) - Reversão à média esperada"
        
        # Análise de volatilidade
        if atr > 0:
            atr_pct = (atr / buy_price * 100)
            if atr_pct > 3.0:
                volatilidade = f"⚡ ALTA ({atr_pct:.2f}%) - Stop Loss ajustado"
            elif atr_pct > 1.5:
                volatilidade = f"📊 MODERADA ({atr_pct:.2f}%) - Configuração ideal"
            else:
                volatilidade = f"🔒 BAIXA ({atr_pct:.2f}%) - Stop Loss apertado"
        else:
            volatilidade = "📊 Dados insuficientes"
        
        # Fonte dos dados
        fonte_dados = "📡 *FONTES DOS DADOS:*\n"
        fonte_dados += "• Preço/Volume: Binance API (tempo real)\n"
        fonte_dados += "• Indicadores: Scalper Blindado (RSI, BB, ADX, ATR)\n"
        fonte_dados += "• Sentimento: CEO Manager (Fear & Greed Index)\n"
        if pos_info.get('sl_dinamico'):
            fonte_dados += "• SL/TP: IA Dinâmica (ATR + ADX + Sentimento)\n"
        else:
            fonte_dados += "• SL/TP: Valores fixos (Sandra Mode)\n"
        
        # Confluência de sinais
        confluencia = "🎯 *CONFLUÊNCIA DE SINAIS:*\n"
        pontos = 0
        
        if rsi < 20:
            confluencia += f"✅ RSI {rsi:.1f} < 20 (EXTREMO) +3pts\n"
            pontos += 3
        elif rsi < 25:
            confluencia += f"✅ RSI {rsi:.1f} < 25 (FORTE) +2pts\n"
            pontos += 2
        elif rsi < 30:
            confluencia += f"✅ RSI {rsi:.1f} < 30 (PADRÃO) +1pt\n"
            pontos += 1
        else:
            confluencia += f"⚠️ RSI {rsi:.1f} (sem bônus)\n"
        
        if bb_lower > 0 and buy_price <= bb_lower * 1.02:
            confluencia += f"✅ Preço na Banda Inferior (sobrevenda) +1pt\n"
            pontos += 1
        
        if sentiment == "BEAR":
            confluencia += f"✅ Mercado em PÂNICO (compra contra-tendência) +2pts\n"
            pontos += 2
        elif sentiment == "NEUTRO":
            confluencia += f"• Sentimento neutro +1pt\n"
            pontos += 1
        
        confluencia += f"\n📊 *Total: {pontos} pontos* "
        if pontos >= 6:
            confluencia += "→ OPORTUNIDADE MÁXIMA 💎"
        elif pontos >= 4:
            confluencia += "→ SINAL FORTE 🔥"
        elif pontos >= 2:
            confluencia += "→ SINAL PADRÃO 🚀"
        else:
            confluencia += "→ Sinal fraco"
        
        # Monta mensagem completa
        msg = f"🚨 *DECISÃO DA IA: NOVA POSIÇÃO* 🚨\n\n"
        msg += f"🪙 *Ativo:* {symbol} ({tier})\n"
        msg += f"✅ *Ação:* COMPRA\n"
        msg += f"💵 *Preço:* ${buy_price:.4f}\n"
        msg += f"📦 *Quantidade:* {buy_qty:.4f}\n"
        msg += f"💰 *Investido:* ${buy_total:.2f}\n"
        msg += f"💸 *Taxa:* -${taxa_est:.3f}\n\n"
        
        msg += f"🧠 *JUSTIFICATIVA TÉCNICA:*\n"
        msg += f"📉 RSI: {rsi:.1f} (sobrevendido)\n"
        msg += f"{tendencia}\n"
        msg += f"⚡ Volatilidade: {volatilidade}\n"
        msg += f"📊 Sentimento: {sentimento_texto}\n"
        msg += f"💡 Motivo: {scalper_reason}\n\n"
        
        msg += confluencia + "\n\n"
        
        msg += f"🎯 *GESTÃO DE RISCO:*\n"
        if pos_info.get('sl_dinamico'):
            msg += f"🧠 Modo: IA DINÂMICA (adaptado)\n"
        else:
            msg += f"📌 Modo: FIXO (Sandra Mode)\n"
        msg += f"🛑 Stop Loss: {sl_usado:.2f}% (${preco_sl:.4f})\n"
        msg += f"✅ Take Profit: {tp_usado:.2f}% (${preco_tp:.4f})\n"
        msg += f"📊 R:R: {abs(tp_usado/sl_usado):.2f}:1\n\n"
        
        msg += fonte_dados + "\n"
        msg += f"⏰ Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        
        return msg
        
    except Exception as e:
        print(f"⚠️ Erro ao gerar justificativa: {e}")
        # Fallback: mensagem simples
        return (
            f"🔵 *COMPRA EXECUTADA* | {symbol}\n\n"
            f"💵 Preço: ${buy_price:.4f}\n"
            f"📦 Qtd: {buy_qty:.4f}\n"
            f"📉 RSI: {rsi:.1f}\n\n"
            f"🎯 SL: {sl_usado:.2f}% | TP: {tp_usado:.2f}%"
        )


def execute_real_trade(action, price, symbol, reason=None, amount_usdt=None):
    """Executa trade REAL na Binance (Suporte a MÚLTIPLAS POSIÇÕES; máx 3)."""
    if not exchange or not API_KEY or not SECRET:
        print("⚠️ Modo real desabilitado: sem chaves API")
        return False
    
    try:
        with state_lock:
            strategy_key = lab_state.get('selected_strategy', 'aggressive')
            strategy = lab_state['strategies'][strategy_key]

            # Migração automática: position (antigo) -> positions (novo)
            if 'positions' not in strategy or not isinstance(strategy.get('positions'), dict):
                strategy['positions'] = {}
            if strategy.get('position') and isinstance(strategy.get('position'), dict):
                pos_old = strategy.get('position')
                pos_sym = pos_old.get('symbol')
                if pos_sym and pos_sym not in strategy['positions']:
                    strategy['positions'][pos_sym] = pos_old
                strategy['position'] = None

            rsi_snapshot = float(lab_state.get('indicators', {}).get('rsi', 0.0) or 0.0)
            last_trade_snapshot = lab_state.get('last_trade_time', 0)

        def _safe_amount(symbol: str, amount: float) -> float:
            try:
                return float(exchange.amount_to_precision(symbol, amount))
            except Exception:
                return float(amount)

        def market_buy_by_quote(symbol: str, quote_usdt: float, price_hint: float):
            try:
                return ex(exchange.create_market_buy_order, symbol, 0, {"quoteOrderQty": float(quote_usdt)})
            except Exception:
                pass
            try:
                return ex(exchange.create_order, symbol, 'market', 'buy', 0, None, {"quoteOrderQty": float(quote_usdt)})
            except Exception:
                qty = (float(quote_usdt) / float(price_hint)) * 0.995
                try:
                    qty = float(exchange.amount_to_precision(symbol, qty))
                except Exception:
                    pass
                return ex(exchange.create_market_buy_order, symbol, qty)

        def _block(block_reason: str):
            try:
                with state_lock:
                    payload = {
                        'ts': now_iso(),
                        'action': action,
                        'symbol': symbol,
                        'reason': str(block_reason),
                    }
                    lab_state['last_trade_block'] = payload
                    lab_state.setdefault('last_trade_block_by_symbol', {})[symbol] = payload
            except Exception:
                pass
            return False

        def _refresh_primary_position():
            try:
                with state_lock:
                    # Mantém compatibilidade: strategy['position'] aponta para "uma" posição
                    positions = strategy.get('positions', {}) or {}
                    if positions:
                        any_symbol = next(iter(positions))
                        strategy['position'] = positions.get(any_symbol)
                    else:
                        strategy['position'] = None
            except Exception:
                pass

        if action == 'buy':
            desired = float(amount_usdt if amount_usdt is not None else AMOUNT_INVEST)
            desired = min(desired, SANDRA["MAX_BET"])

            # Limite de posições simultâneas
            with state_lock:
                positions = strategy.get('positions', {}) or {}
                if symbol in positions:
                    return _block("Já existe posição aberta nesse par")
                if len(positions) >= 3:
                    return _block("Limite de posições atingido (3/3)")

            # Min notional
            min_notional = get_min_notional_usdt(symbol, fallback=10.0)
            with state_lock:
                drawdown_mode = bool(GLOBAL_STATS.get('drawdown_mode', False))

            if drawdown_mode and desired < min_notional:
                print(f"🛡️ Proteção ativa: ordem ${desired:.2f} < mínimo ${min_notional:.2f}. Não opera.")
                send_telegram_message(f"🛡️ Proteção ativa: aposta abaixo do mínimo do par.")
                return _block(f"Proteção ativa: ordem ${desired:.2f} < mínimo ${min_notional:.2f}")
            if desired < min_notional:
                print(f"⚠️ Ordem abaixo do mínimo (${desired:.2f} < ${min_notional:.2f}). Pulando.")
                return _block(f"Ordem abaixo do mínimo: ${desired:.2f} < ${min_notional:.2f}")

            # === COOLDOWN DE 15 MINUTOS (CORREÇÃO APLICADA) ===
            current_time = time.time()
            
            # 1. Verifica cooldown específico deste par (900s = 15min)
            last_symbol_trade = lab_state.get('symbol_cooldowns', {}).get(symbol, 0)
            SYMBOL_COOLDOWN = 900 

            if current_time - last_symbol_trade < SYMBOL_COOLDOWN:
                # Silencioso no log para não poluir, mas impede a compra
                return _block("Cooldown do par (15min)")

            # 2. Cooldown Global de Segurança (60s entre qualquer trade)
            GLOBAL_COOLDOWN = 60
            if current_time - last_trade_snapshot < GLOBAL_COOLDOWN:
                return _block("Cooldown global (60s)")

            # Busca Saldo Real
            balance = ex(exchange.fetch_balance)
            usdt_balance = balance.get('free', {}).get('USDT', 0.0)
            print(f"💳 Saldo REAL da Binance: ${usdt_balance:.2f} USDT")
            
            with state_lock:
                lab_state['real_balance'] = usdt_balance
                try:
                    lab_state.setdefault('user_info', {})['usdt_total'] = float(balance.get('total', {}).get('USDT', usdt_balance))
                except: pass
            
            required = desired * (1 + FEE_RATE)

            if usdt_balance < required:
                print(f"⚠️ USDT insuficiente. Tentando converter BRL...")
                usdt_balance = convert_brl_to_usdt()
                if usdt_balance < required:
                    print(f"⚠️ Saldo insuficiente: ${usdt_balance:.2f}")
                    return _block(f"Saldo insuficiente: ${usdt_balance:.2f} < ${required:.2f}")

            invest_amount = desired

            # EXECUTA COMPRA
            order = market_buy_by_quote(symbol=symbol, quote_usdt=invest_amount, price_hint=price)
            
            buy_price = order['average'] or price
            buy_qty = order['filled']
            buy_total = buy_price * buy_qty
            rsi = rsi_snapshot

            with state_lock:
                trade = {
                    'timestamp': now_iso(),
                    'side': 'buy',
                    'symbol': symbol,
                    'price': buy_price,
                    'qty': buy_qty,
                    'fees': buy_total * FEE_RATE,
                    'mode': 'REAL',
                    'rsi': rsi,
                    'time': now_sp().strftime('%H:%M:%S'),
                    'type': f'BUY REAL ({symbol})',
                    'order_id': order.get('id', ''),
                    'profit_pct': 0,
                }
                strategy['trades'].append(trade)

                new_pos = {
                    'symbol': symbol,
                    'entry_price': buy_price,
                    'qty': buy_qty,
                    'entry_time': now_iso(),
                    'highest_price': buy_price,
                    'trail_active': False,
                    'entry_cost_usdt': buy_total,
                    'entry_fee_usdt': buy_total * FEE_RATE,
                    'entry_rsi': rsi,
                    'log_entry': f"Compra em {now_sp().strftime('%H:%M')} | RSI: {rsi:.1f}",
                }
                
                # 🧠 INTELIGÊNCIA ARTIFICIAL: Calcula SL/TP dinâmico no momento da compra
                try:
                    if SANDRA.get("USE_DYNAMIC_RISK", False):
                        # Busca dados do mercado para IA
                        market_data = lab_state.get('market_overview', {}).get(symbol, {})
                        atr = market_data.get('atr', 0.0)
                        adx = market_data.get('adx', 0.0)
                        
                        # Busca sentimento de mercado
                        try:
                            sentiment, _ = ceo_manager.get_market_sentiment()
                        except Exception:
                            sentiment = "NEUTRO"
                        
                        # Calcula SL dinâmico (ATR + ADX + Sentimento)
                        if atr and atr > 0:
                            atr_pct = (atr / buy_price * 100) if buy_price > 0 else 0.0
                            sl_dinamico = ceo_manager.calcular_sl_dinamico(atr_pct, adx, sentiment)
                            new_pos['sl_dinamico'] = sl_dinamico
                            
                            # Calcula TP dinâmico (garante R:R >= 1.5:1)
                            tp_dinamico = ceo_manager.calcular_tp_dinamico(sl_dinamico, adx, rsi, sentiment)
                            new_pos['tp_dinamico'] = tp_dinamico
                            
                            print(f"🧠 IA: SL={sl_dinamico:.2f}% | TP={tp_dinamico:.2f}% | ATR={atr_pct:.2f}% | ADX={adx:.1f} | Sentimento={sentiment}")
                        else:
                            print(f"⚠️ ATR inválido ({atr}), usando SL/TP fixos")
                except Exception as e:
                    print(f"⚠️ Erro ao calcular SL/TP dinâmico: {e}")
                
                strategy.setdefault('positions', {})
                strategy['positions'][symbol] = new_pos
            
            print(f"💰 [{strategy['name']}] COMPRA REAL: {buy_qty:.4f} {symbol} @ ${buy_price:.4f}")
            taxa_est = buy_total * FEE_RATE

            # Busca SL/TP da posição (dinâmico ou fixo)
            with state_lock:
                pos_info = strategy['positions'].get(symbol, {})
                sl_usado = pos_info.get('sl_dinamico', SANDRA.get('STOP_BASE', -3.0))
                tp_usado = pos_info.get('tp_dinamico', SANDRA.get('TP_SLOW', 5.0))
                
            # Preços alvo
            preco_sl = buy_price * (1 + sl_usado / 100)
            preco_tp = buy_price * (1 + tp_usado / 100)
            
            # 🧠 GERA JUSTIFICATIVA INTELIGENTE DA IA
            justificativa_msg = _gerar_justificativa_compra(
                symbol=symbol,
                rsi=rsi,
                buy_price=buy_price,
                buy_qty=buy_qty,
                buy_total=buy_total,
                taxa_est=taxa_est,
                sl_usado=sl_usado,
                tp_usado=tp_usado,
                preco_sl=preco_sl,
                preco_tp=preco_tp,
                pos_info=pos_info,
                reason=reason
            )

            # Envia mensagem completa (assíncrono para não atrasar trading)
            send_telegram_message(justificativa_msg)
            send_chart_to_telegram(symbol, caption="📊 Gráfico no momento da COMPRA")
            
            # ATUALIZA TODOS OS COOLDOWNS (CORREÇÃO APLICADA)
            with state_lock:
                lab_state['last_trade_time'] = time.time()
                # Grava o cooldown específico do par SEMPRE
                lab_state.setdefault('symbol_cooldowns', {})[symbol] = time.time()

            _refresh_primary_position()
            
            return True

        elif action == 'sell':
            # Venda por símbolo (multi-posições)
            with state_lock:
                positions = strategy.get('positions', {}) or {}
                pos = positions.get(symbol)
                if not pos and strategy.get('position') and isinstance(strategy.get('position'), dict):
                    # compatibilidade: se vier do formato antigo
                    if strategy['position'].get('symbol') == symbol:
                        pos = strategy['position']
                        strategy.setdefault('positions', {})
                        strategy['positions'][symbol] = pos
                        strategy['position'] = None

            if pos:
                qty = pos.get('qty', 0)
                
                try:
                    balance = ex(exchange.fetch_balance)
                    coin = symbol.split('/')[0]
                    coin_balance = balance['free'].get(coin, 0)
                    
                    if coin_balance <= 0:
                        with state_lock:
                            try:
                                if symbol in strategy.get('positions', {}):
                                    del strategy['positions'][symbol]
                            except Exception:
                                pass
                            strategy['position'] = None
                        send_telegram_message(f"⚠️ *POSIÇÃO LIMPA* (Sem saldo de {coin})")
                        _refresh_primary_position()
                        return False
                    
                    if coin_balance < qty:
                        qty = coin_balance
                    
                except Exception as e:
                    print(f"⚠️ Erro saldo venda: {e}")

                # Garante que markets estão carregados para precisão correta
                try:
                    if not exchange.markets:
                        exchange.load_markets()
                except Exception:
                    pass

                qty = _safe_amount(symbol, qty)
                
                # === CORREÇÃO CRÍTICA: Validação de Mínimos da Binance ===
                try:
                    market = exchange.market(symbol)
                    min_amount = market['limits']['amount']['min']
                    
                    if qty < min_amount:
                        print(f"⚠️ Quantidade {qty} menor que o mínimo {min_amount}.")
                        
                        # Se o saldo real na carteira for menor que o mínimo, é DUST (poeira)
                        # Devemos limpar a posição do sistema para não ficar travado tentando vender
                        if coin_balance < min_amount:
                            print(f"🧹 Detectado DUST de {symbol} ({coin_balance}). Removendo posição interna.")
                            with state_lock:
                                if symbol in strategy.get('positions', {}):
                                    del strategy['positions'][symbol]
                                # Se era a posição principal
                                if strategy.get('position') and strategy['position'].get('symbol') == symbol:
                                    strategy['position'] = None
                            
                            send_telegram_message(f"🧹 *POSIÇÃO REMOVIDA (DUST)*\nSaldo {coin_balance} < Mínimo {min_amount}")
                            _refresh_primary_position()
                        
                        return False
                except Exception as e:
                    print(f"⚠️ Erro validação min_amount: {e}")
                    # Fallback de segurança: se qty for muito pequeno e não conseguimos validar, aborta
                    if qty < 0.001: 
                        return False
                
                if qty <= 0: return False

                order = ex(exchange.create_market_sell_order, symbol, qty)
                print("⏳ Aguardando confirmação da Binance...")
                time.sleep(5)

                entry_price = pos.get('entry_price', price)
                entry_qty = float(pos.get('qty', qty) or qty)
                
                sell_price = order['average'] or price
                sell_qty = order['filled']
                
                # Cálculo de Lucro Líquido
                ratio = min(1.0, sell_qty / entry_qty) if entry_qty > 0 else 1.0
                entry_cost = float(pos.get('entry_cost_usdt', entry_price * entry_qty)) * ratio
                entry_fee = float(pos.get('entry_fee_usdt', entry_cost * FEE_RATE)) * ratio
                
                sell_gross = sell_price * sell_qty
                sell_fee = sell_gross * FEE_RATE
                sell_net = sell_gross - sell_fee
                
                lucro_liquido_usdt = sell_net - (entry_cost + entry_fee)
                base = (entry_cost + entry_fee)
                lucro_liquido_pct = (lucro_liquido_usdt / base) * 100 if base > 0 else 0.0
                taxas_totais = entry_fee + sell_fee

                # Atualiza saldo
                try:
                    balance = ex(exchange.fetch_balance)
                    usdt_free = balance.get('free', {}).get('USDT', 0.0)
                    with state_lock:
                        lab_state['real_balance'] = usdt_free
                        try: lab_state['user_info']['usdt_total'] = float(balance.get('total', {}).get('USDT', usdt_free))
                        except: pass
                except: pass

                with state_lock:
                    trade = {
                        'timestamp': now_iso(),
                        'side': 'sell',
                        'symbol': symbol,
                        'entry_price': entry_price,
                        'exit_price': sell_price,
                        'qty': sell_qty,
                        'fees': taxas_totais,
                        'net_profit_usdt': lucro_liquido_usdt,
                        'net_profit_pct': lucro_liquido_pct,
                        'reason': reason or '',
                        'mode': 'REAL',
                        'rsi': rsi_snapshot,
                        'time': now_sp().strftime('%H:%M:%S'),
                        'type': f'SELL REAL ({symbol})',
                        'profit_pct': lucro_liquido_pct,
                    }
                    strategy['trades'].append(trade)

                    # Histórico eterno (SQLite)
                    try:
                        db_record_trade(strategy.get('name', selected), trade)
                        db_record_event('trade', f"BUY {symbol}", data={'side': 'buy', 'symbol': symbol})
                    except Exception:
                        pass
                    try:
                        if symbol in strategy.get('positions', {}):
                            del strategy['positions'][symbol]
                    except Exception:
                        pass
                    strategy['position'] = None
                    
                    # 🧠 LÓGICA SÁBIA: Registra SL para bloqueio inteligente de recompra
                    if reason and "STOP" in reason.upper():
                        strategy.setdefault('last_sl_time', {})[symbol] = time.time()
                        print(f"⛔ STOP LOSS registrado para {symbol} - Cooldown estendido ativado")

                # Histórico eterno (SQLite) + backup do DB após venda
                try:
                    db_record_trade(strategy.get('name', selected), trade)
                    db_record_event('trade', f"SELL {symbol}", data={'side': 'sell', 'symbol': symbol, 'net_profit_usdt': lucro_liquido_usdt})
                    maybe_backup_db(reason=f"sell:{symbol}")
                except Exception:
                    pass
                
                print(f"💵 VENDA: {symbol} | Líquido: ${lucro_liquido_usdt:+.2f}")
                
                with state_lock:
                    today = now_sp().strftime('%Y-%m-%d')
                    if lab_state['pnl']['date'] != today:
                        lab_state['pnl']['date'] = today
                        lab_state['pnl']['day_net'] = 0.0
                    lab_state['pnl']['day_net'] += lucro_liquido_usdt
                    lab_state['pnl']['total_net'] += lucro_liquido_usdt

                icon = "✅" if lucro_liquido_usdt > 0 else "🔻"
                msg = (
                    f"{icon} *VENDA FINALIZADA* | {symbol}\n"
                    f"Motivo: _{reason or 'Sinal de Saída'}_ \n\n"
                    f"📥 Comprou: ${entry_price:.4f}\n"
                    f"📤 Vendeu:  ${sell_price:.4f}\n\n"
                    f"🧾 *Contabilidade:*\n"
                    f"Valor Bruto:  ${sell_gross:.2f}\n"
                    f"(-) Custo:    ${entry_cost:.2f}\n"
                    f"(-) Taxas:    ${taxas_totais:.3f}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"💰 *LÍQUIDO: ${lucro_liquido_usdt:+.2f} ({lucro_liquido_pct:+.2f}%)*\n\n"
                    f"📅 Dia: ${lab_state['pnl']['day_net']:+.2f}"
                )
                send_telegram_message(msg)
                send_chart_to_telegram(symbol, caption="Gráfico no momento da VENDA")
                update_sandra_streak(lucro_liquido_usdt)
                _refresh_primary_position()
                return True

    except Exception as e:
        print(f"❌ ERRO ORDEM REAL: {e}")
        send_telegram_message(f"❌ *ERRO CRÍTICO NA EXECUÇÃO*\n\n{str(e)}")
        return False


def detect_existing_positions():
    """Detecta moedas já existentes na carteira e restaura posições."""
    if not exchange:
        return
    
    try:
        balance = ex(exchange.fetch_balance)
        with state_lock:
            selected = lab_state.get('selected_strategy', 'aggressive')
            strategy = lab_state['strategies'][selected]

            # Migração automática: position (antigo) -> positions (novo)
            if 'positions' not in strategy or not isinstance(strategy.get('positions'), dict):
                strategy['positions'] = {}
            if strategy.get('position') and isinstance(strategy.get('position'), dict):
                pos_old = strategy.get('position')
                pos_sym = pos_old.get('symbol')
                if pos_sym and pos_sym not in strategy['positions']:
                    strategy['positions'][pos_sym] = pos_old
                strategy['position'] = None

            # Se já tem posições registradas, não tenta restaurar
            if strategy.get('positions'):
                return
        
        # Procura por moedas na carteira que estão na WATCHLIST (até 3 posições)
        restored = 0
        for symbol in WATCHLIST:
            coin = symbol.replace('/USDT', '')
            coin_balance = balance['total'].get(coin, 0.0)
            
            if coin_balance > 0:
                # Busca o preço atual
                ticker = ex(exchange.fetch_ticker, symbol)
                current_price = ticker['last']
                coin_value_usdt = coin_balance * current_price
                
                print(f"💰 Encontrado {coin}: {coin_balance:.8f} (${coin_value_usdt:.2f})")
                
                # Se tiver mais de $1 em valor, considera como posição aberta
                if coin_value_usdt >= 1:
                    # Estima o preço de entrada (usa o preço atual como fallback)
                    # Idealmente pegaria do histórico de trades
                    try:
                        trades = ex(exchange.fetch_my_trades, symbol, None, None, 5)
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
                    
                    position = {
                        'entry_price': entry_price,
                        'qty': coin_balance,
                        'entry_time': now_iso(),
                        'symbol': symbol,
                        'highest_price': current_price,
                        'trail_active': False,
                        # estimativa (sem histórico completo) para manter PnL coerente
                        'entry_cost_usdt': float(current_price) * float(coin_balance),
                        'entry_fee_usdt': float(current_price) * float(coin_balance) * FEE_RATE,
                    }
                    with state_lock:
                        st = lab_state['strategies'][selected]
                        st.setdefault('positions', {})
                        if symbol not in st['positions'] and len(st['positions']) < 3:
                            st['positions'][symbol] = position
                            if st.get('position') is None:
                                st['position'] = position
                            restored += 1
                    
                    profit_pct = ((current_price - entry_price) / entry_price) * 100
                    print(f"🔄 POSIÇÃO RESTAURADA: {coin_balance:.6f} {symbol} @ ${entry_price:.2f} (Lucro: {profit_pct:+.2f}%)")
                    # Não envia Telegram aqui para não spammar
                    if restored >= 3:
                        return
                    
    except Exception as e:
        print(f"⚠️ Erro ao detectar posições: {e}")


def rollover_pnl_if_new_day():
    """Zera PnL diário quando virar o dia, mesmo sem trades."""
    today = now_sp().strftime('%Y-%m-%d')
    pnl = lab_state.setdefault('pnl', {'date': today, 'day_net': 0.0, 'total_net': 0.0})
    if pnl.get('date') != today:
        pnl['date'] = today
        pnl['day_net'] = 0.0


def trading_loop():
    """Loop principal do sistema."""
    print("🚀 Loop de trading iniciado")
    load_lab_data()

    # Mescla watchlist dinâmica (Caçador) no runtime
    try:
        with state_lock:
            dyn = lab_state.get('dynamic_watchlist') if isinstance(lab_state.get('dynamic_watchlist'), list) else []
        if dyn:
            added = 0
            for s in dyn:
                if s and s not in WATCHLIST:
                    WATCHLIST.append(s)
                    added += 1
            if added:
                print(f"🔭 CAÇADOR: restauradas {added} moedas na WATCHLIST.")
    except Exception:
        pass
    
    # Detecta posições existentes na carteira ao iniciar
    if lab_state['is_live'] and exchange:
        print("🔍 Verificando posições existentes na carteira...")
        detect_existing_positions()

    # Migração de estado antigo -> novo (safety)
    with state_lock:
        selected = lab_state.get('selected_strategy', 'aggressive')
        st = lab_state['strategies'][selected]
        if 'positions' not in st or not isinstance(st.get('positions'), dict):
            st['positions'] = {}
        if st.get('position') and isinstance(st.get('position'), dict):
            pos_old = st.get('position')
            pos_sym = pos_old.get('symbol')
            if pos_sym and pos_sym not in st['positions']:
                st['positions'][pos_sym] = pos_old
            st['position'] = None

    last_ceo_check = 0.0

    while True:
        try:
            if time.time() - last_ceo_check > 3600:
                print("👔 CEO: Consultando o mercado...")
                try:
                    sentiment, fng_val = ceo_manager.get_market_sentiment()
                    new_strat = ceo_manager.calculate_dynamic_strategy(sentiment, fng_val)

                    with state_lock:
                        SANDRA["ENTRY_RSI"] = new_strat["ENTRY_RSI"]
                        SANDRA["STOP_BASE"] = new_strat["STOP_BASE"]
                        SANDRA["ENTRY_TOL"] = new_strat["ENTRY_TOL"]

                    msg_ceo = (
                        "🧠 CEO ATUALIZOU A ESTRATEGIA:\n"
                        f"   Modo: {new_strat['MODE']} (Indice Medo: {fng_val})\n"
                        f"   Novo RSI Entrada: < {SANDRA['ENTRY_RSI']}\n"
                        f"   Novo Stop: {SANDRA['STOP_BASE']}%"
                    )
                    print(msg_ceo)
                    send_telegram_message(msg_ceo)
                except Exception as e:
                    print(f"⚠️ CEO falhou, mantendo parametros atuais: {e}")
                last_ceo_check = time.time()

            rollover_pnl_if_new_day()

            # Fechamento diário (E-mail + Telegram)
            maybe_send_daily_email_report()

            # CONTROLE DO CAÇADOR (a cada N segundos)
            try:
                intervalo = int(os.getenv('CACADOR_INTERVAL_S', '1800'))
            except Exception:
                intervalo = 1800

            agora = time.time()
            with state_lock:
                ultimo_caca = float(lab_state.get('last_hunt_time', 0) or 0)

            if agora - ultimo_caca >= intervalo:
                novas = cacador_de_gemas()
                with state_lock:
                    lab_state['last_hunt_time'] = agora
                if novas:
                    save_lab_data()

            # MULTI: sempre varre a WATCHLIST inteira
            target_coins = list(WATCHLIST)
            
            # 🧠 ATUALIZA SENTIMENTO DO MERCADO (F&G Index) - Armazena no lab_state para IA consultar
            try:
                sentiment, fng_value = ceo_manager.get_market_sentiment()
                with state_lock:
                    lab_state['market_sentiment'] = {
                        'sentiment': sentiment,  # "BEAR", "NEUTRO", "BULL"
                        'fng_value': fng_value,  # 0-100
                        'last_update': now_iso()
                    }
            except Exception as e:
                print(f"⚠️ Erro ao atualizar sentimento: {e}")
            
            # ATUALIZA SALDO ANTES de verificar sinais de compra
            if exchange and API_KEY:
                try:
                    balance = cached_fetch_balance(ttl_s=3.0)
                    usdt_free = balance.get('free', {}).get('USDT', 0.0)
                    usdt_total = balance.get('total', {}).get('USDT', 0.0)
                    with state_lock:
                        lab_state['real_balance'] = usdt_free
                        lab_state['brl_balance'] = balance.get('total', {}).get('BRL', 0.0)
                        lab_state.setdefault('user_info', {})
                        lab_state['user_info']['usdt_free'] = usdt_free
                        lab_state['user_info']['usdt_total'] = usdt_total
                        
                        # 💰 ATUALIZA FATOR DE JURO COMPOSTO
                        saldo_atual = usdt_free
                        fator_escala = max(1.0, saldo_atual / SALDO_BASE)
                        lab_state['compound_interest'] = {
                            'saldo_base': SALDO_BASE,
                            'saldo_atual': saldo_atual,
                            'fator_escala': fator_escala,
                            'last_update': now_iso()
                        }
                except Exception as e:
                    print(f"⚠️ Erro ao atualizar saldo: {e}")

            for current_symbol in target_coins:
                # 1. Busca dados brutos e processa no CÉREBRO (Scalper Blindado)
                # Usa fetch_raw_candles para pegar lista de klines
                raw_klines = fetch_raw_candles(current_symbol, interval='5m', limit=100)
                
                if not raw_klines:
                    continue

                # Chama o cérebro (Scalper Blindado)
                # Ele retorna (Sinal:bool, Motivo:str, Indicadores:dict)
                sinal_compra_blindado, motivo_blindado, indicadores = scalper_blindado.analisar_sinal_hibrido(raw_klines, current_symbol)
                
                # Extrai dados para compatibilidade com o resto do sistema
                price = indicadores.get('price')
                rsi = indicadores.get('rsi')
                bb_lower = indicadores.get('bb_lower')
                bb_upper = indicadores.get('bb_upper')
                vol_now = indicadores.get('vol_now')
                adx = indicadores.get('adx')
                atr = indicadores.get('atr')
                
                # Calcula vol_avg (média 20) manualmente pois o scalper não retorna isso ainda
                try:
                    volumes = [float(k[5]) for k in raw_klines]
                    vol_avg = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
                except:
                    vol_avg = 0.0

                # Alerta precoce — avisa antes de apertar o gatilho
                if price is not None and rsi is not None and bb_lower is not None:
                    if rsi < 40 and price <= bb_lower * 1.02:  # até 2% acima da banda
                        send_opportunity_alert(
                            current_symbol,
                            price,
                            rsi,
                            bb_lower,
                            scalper_ok=bool(sinal_compra_blindado),
                            scalper_reason=motivo_blindado,
                        )

                if price is not None:
                    with state_lock:
                        lab_state['current_price'] = price
                        lab_state['current_symbol'] = current_symbol # Atualiza o símbolo na interface
                        lab_state['last_update'] = datetime.now().strftime('%H:%M:%S')
                        
                        # Atualiza indicadores globais
                        lab_state['indicators']['rsi'] = rsi
                        lab_state['indicators']['bb_lower'] = bb_lower
                        lab_state['indicators']['bb_upper'] = bb_upper
                    
                    # Verifica BTC caindo >2% em 15min (cache 20s)
                    btc_is_dumping_15m = btc_drop_15m_cached()
                    
                    # Verifica BTC sangrando 3 dias (cache 1h)
                    btc_bleeding = btc_bleeding_3days_cached()
                    
                    # Atualiza Radar de Mercado + Diagnóstico
                    with state_lock:
                        selected_strategy = lab_state['selected_strategy']
                        st = lab_state['strategies'][selected_strategy]
                        st.setdefault('positions', {})
                        strategy_position = st['positions'].get(current_symbol)
                    diagnostic = get_diagnostic(selected_strategy, price, rsi, bb_lower, strategy_position)

                    with state_lock:
                        lab_state['market_overview'][current_symbol] = {
                            'price': price,
                            'rsi': rsi,
                            'adx': adx,
                            'atr': atr,
                            'bb_lower': bb_lower,
                            'bb_upper': bb_upper,
                            'diagnostic': diagnostic,
                            'last_update': datetime.now().strftime('%H:%M:%S')
                        }
                        
                        # Atualiza diagnósticos separados por moeda
                        lab_state['diagnostics'][current_symbol] = diagnostic

                        # Guarda a última decisão/sinal por moeda (para auditoria/IA)
                        lab_state.setdefault('last_decisions', {})[current_symbol] = {
                            'ts': now_iso(),
                            'price': price,
                            'rsi': rsi,
                            'bb_lower': bb_lower,
                            'bb_upper': bb_upper,
                            'diagnostic': diagnostic,
                            'scalper_ok': bool(sinal_compra_blindado),
                            'scalper_reason': motivo_blindado,
                            'buy_attempted': False,
                            'buy_result': None,
                            'block_reason': None,
                        }

                # 2. Lógica de Trading (Apenas se estiver RODANDO)
                with state_lock:
                    running = lab_state.get('running', False)
                if running:
                    with state_lock:
                        lab_state['status'] = f'Rodando 🚀 | {current_symbol}'

                    if price is not None:
                        # LOG DE ANÁLISE
                        with state_lock:
                            current_balance = lab_state.get('real_balance', 0.0)
                        print(f"🔎 {current_symbol}: RSI={rsi:.1f} | Preço=${price:.2f} | Saldo=${current_balance:.2f}")
                        
                        if sinal_compra_blindado:
                            print(f"🧠 SCALPER BLINDADO APROVOU: {motivo_blindado}")

                        # ========== 2.1 MODO REAL PRIMEIRO! ==========
                        with state_lock:
                            is_live = lab_state.get('is_live', False)
                            selected = lab_state.get('selected_strategy', 'aggressive')
                            strategy = lab_state['strategies'][selected]
                            strategy.setdefault('positions', {})
                            open_positions = dict(strategy.get('positions') or {})
                        if is_live:

                            if current_symbol not in open_positions:
                                # Sem posição NESTA moeda - procura oportunidade de COMPRA
                                
                                # Atualiza controle de drawdown (perdeu 10% do topo?) usando EQUITY
                                with state_lock:
                                    usdt_total = float(lab_state.get('user_info', {}).get('usdt_total', lab_state.get('real_balance', 0.0)) or 0.0)
                                    equity = usdt_total  # Sem posição = só USDT (mais estável)
                                    if equity > GLOBAL_STATS['peak_balance']:
                                        GLOBAL_STATS['peak_balance'] = equity
                                        GLOBAL_STATS['drawdown_mode'] = False
                                    elif equity < GLOBAL_STATS['peak_balance'] * 0.9:
                                        GLOBAL_STATS['drawdown_mode'] = True
                                        print(f"🛡️ MODO PROTEÇÃO: Equity caiu 10% (${equity:.2f} < ${GLOBAL_STATS['peak_balance'] * 0.9:.2f})")
                                
                                # --- INTEGRAÇÃO DO CÉREBRO + IA DINÂMICA ---
                                invest_amount = 0.0
                                
                                # Se o Scalper Blindado der sinal VERDADEIRO, entramos!
                                if sinal_compra_blindado and not btc_bleeding:
                                    
                                    # 🧠 LÓGICA SÁBIA: Bloqueia recompra após SL se tendência de baixa for forte
                                    with state_lock:
                                        last_sl_times = strategy.get('last_sl_time', {})
                                        if current_symbol in last_sl_times:
                                            last_sl_time = last_sl_times[current_symbol]
                                            current_time = time.time()
                                            time_since_sl = current_time - last_sl_time
                                            
                                            # Cooldown de 4 horas (14400 segundos)
                                            COOLDOWN_ESTENDIDO = 4 * 3600  # 4 horas
                                            
                                            if time_since_sl < COOLDOWN_ESTENDIDO:
                                                # Verifica ADX (força da tendência)
                                                adx_atual = indicadores.get('adx', 0.0)
                                                
                                                if adx_atual > 25:
                                                    # Bloqueio inteligente ativado
                                                    tempo_restante_min = (COOLDOWN_ESTENDIDO - time_since_sl) / 60
                                                    print(f"⛔ BLOQUEIO SÁBIO: {current_symbol}")
                                                    print(f"   • SL recente há {time_since_sl/60:.0f} min")
                                                    print(f"   • ADX={adx_atual:.1f} (tendência forte de baixa)")
                                                    print(f"   • Cooldown restante: {tempo_restante_min:.0f} min")
                                                    
                                                    with state_lock:
                                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                                        lab_state['last_decisions'][current_symbol].update({
                                                            'buy_attempted': False,
                                                            'buy_result': False,
                                                            'block_reason': f'Bloqueio Sábio: SL recente + Tendência Forte (ADX={adx_atual:.1f})',
                                                        })
                                                    
                                                    # Pula para próxima moeda
                                                    continue
                                    
                                    # 🧠 IA DINÂMICA: Calcula tamanho da aposta baseado em confluências
                                    try:
                                        rsi_val = indicadores.get('rsi', 50)
                                        vol_ratio = indicadores.get('vol_ratio', 1.0)
                                        atr_val = indicadores.get('atr', 0.0)
                                        
                                        # Busca sentimento de mercado
                                        try:
                                            sentiment, _ = ceo_manager.get_market_sentiment()
                                        except Exception:
                                            sentiment = "NEUTRO"
                                        
                                        # 💰 JURO COMPOSTO: Calcula fator de escala baseado no saldo atual
                                        saldo_atual = lab_state.get('real_balance', SALDO_BASE)
                                        fator_escala = max(1.0, saldo_atual / SALDO_BASE)  # Nunca menor que 1.0
                                        base_bet_escalada = 11.0 * fator_escala
                                        
                                        # Calcula aposta inteligente (considera RSI + Volume + Sentimento + ATR + Juro Composto)
                                        invest_amount = ceo_manager.calcular_tamanho_aposta(
                                            rsi_value=rsi_val,
                                            volume_ratio=vol_ratio,
                                            sentiment=sentiment,
                                            atr_value=atr_val,
                                            base_bet=base_bet_escalada
                                        )
                                        
                                        if invest_amount >= 33.0:
                                            print(f"💎 🧠 IA: SINAL EXCEPCIONAL! Aposta ${invest_amount:.2f}")
                                            print(f"   Confluências: RSI={rsi_val:.1f} | Volume={vol_ratio:.2f}x | Sentimento={sentiment} | ATR={atr_val:.2f}")
                                            print(f"   💰 Fator de Escala (Juro Composto): {fator_escala:.2f}x (Saldo: ${saldo_atual:.2f})")
                                        elif invest_amount >= 22.0:
                                            print(f"🔥 🧠 IA: SINAL FORTE! Aposta ${invest_amount:.2f}")
                                            print(f"   Confluências: RSI={rsi_val:.1f} | Volume={vol_ratio:.2f}x | Sentimento={sentiment}")
                                            print(f"   💰 Fator de Escala: {fator_escala:.2f}x")
                                        elif invest_amount >= 11.0:
                                            print(f"🚀 🧠 IA: SINAL PADRÃO! Aposta ${invest_amount:.2f}")
                                            print(f"   RSI={rsi_val:.1f} | 💰 Escala: {fator_escala:.2f}x")
                                        else:
                                            print(f"⚠️ 🧠 IA: Sinal fraco, não aposta (pontuação baixa)")
                                        
                                        print(f"🧠 Motivo Scalper: {motivo_blindado}")
                                        
                                    except Exception as e:
                                        # Fallback: lógica antiga
                                        print(f"⚠️ Erro na IA de apostas, usando lógica clássica: {e}")
                                        rsi_val = indicadores.get('rsi', 50)
                                        if rsi_val < 20:
                                            invest_amount = 33.0
                                        elif rsi_val < 25:
                                            invest_amount = 22.0
                                        else:
                                            invest_amount = 11.0

                                if sinal_compra_blindado and btc_bleeding:
                                    with state_lock:
                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                        lab_state['last_decisions'][current_symbol].update({
                                            'buy_attempted': False,
                                            'buy_result': False,
                                            'block_reason': 'Bloqueado: BTC em sangria (3 dias) — filtro de proteção ativo',
                                        })
                                
                                # Mantém lógica antiga como fallback ou secundária? 
                                # O usuário pediu para o scalper ser o cérebro. Vamos priorizar ele.
                                # Se quiser manter a Sandra antiga, pode fazer um OR.
                                # if sinal_compra_blindado or (check_strategy_signal(...) > 0): ...
                                
                                # Máx 3 posições
                                if invest_amount > 0 and len(open_positions) >= 3:
                                    with state_lock:
                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                        lab_state['last_decisions'][current_symbol].update({
                                            'buy_attempted': False,
                                            'buy_result': False,
                                            'block_reason': 'Limite de posições atingido (3/3)',
                                        })

                                elif invest_amount > 0 and current_balance >= invest_amount:
                                    print(f"🎯 SINAL DETECTADO: Investir ${invest_amount} em {current_symbol}!")

                                    with state_lock:
                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                        lab_state['last_decisions'][current_symbol].update({
                                            'buy_attempted': True,
                                            'buy_result': None,
                                            'block_reason': None,
                                        })

                                    result = execute_real_trade('buy', price, current_symbol, amount_usdt=invest_amount)

                                    with state_lock:
                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                        lab_state['last_decisions'][current_symbol]['buy_result'] = bool(result)
                                        if not result:
                                            last_block = lab_state.get('last_trade_block_by_symbol', {}).get(current_symbol) or {}
                                            lab_state['last_decisions'][current_symbol]['block_reason'] = (
                                                last_block.get('reason')
                                                or lab_state.get('last_trade_block', {}).get('reason')
                                                or 'Compra não executada (motivo não registrado)'
                                            )

                                    if result:
                                        pass
                                elif invest_amount > 0 and current_balance < invest_amount:
                                    with state_lock:
                                        lab_state.setdefault('last_decisions', {}).setdefault(current_symbol, {})
                                        lab_state['last_decisions'][current_symbol].update({
                                            'buy_attempted': False,
                                            'buy_result': False,
                                            'block_reason': f'Saldo insuficiente: precisa ${invest_amount:.2f} e tem ${current_balance:.2f}',
                                        })
                                elif rsi < 45:
                                    print(f"⏸️ RSI baixo ({rsi:.1f}), aguardando condições de entrada...")
                            else:
                                # TEM POSIÇÃO NESTA moeda - verifica VENDA
                                pos = open_positions.get(current_symbol) or {}
                                entry_price = float(pos.get('entry_price', price) or price)
                                profit_pct = ((price - entry_price) / entry_price) * 100 if entry_price else 0.0

                                # Radar Financeiro (educacional / log): break-even e alvos líquidos (com taxas)
                                try:
                                    qty = float(pos.get('qty', 0) or 0.0)
                                    entry_cost = float(pos.get('entry_cost_usdt', entry_price * qty) or 0.0)
                                    entry_fee = float(pos.get('entry_fee_usdt', entry_cost * FEE_RATE) or 0.0)
                                    total_cost = entry_cost + entry_fee

                                    gross_now = float(price) * qty
                                    sell_fee_now = gross_now * FEE_RATE
                                    net_sell_now = gross_now - sell_fee_now
                                    net_profit_now = net_sell_now - total_cost
                                    net_profit_pct = (net_profit_now / total_cost) * 100 if total_cost > 0 else 0.0

                                    denom = qty * (1 - FEE_RATE)
                                    breakeven_price = (total_cost / denom) if denom > 0 else None

                                    target_net_pct = 0.01  # +1% líquido sobre o custo total
                                    target_price = (total_cost * (1 + target_net_pct) / denom) if denom > 0 else None
                                except Exception:
                                    qty = 0.0
                                    total_cost = 0.0
                                    net_profit_now = 0.0
                                    net_profit_pct = 0.0
                                    breakeven_price = None
                                    target_price = None

                                print(
                                    f"📍 POSIÇÃO ATIVA: {current_symbol} | Entrada: ${entry_price:.4f} | Atual: ${price:.4f} | Lucro (bruto): {profit_pct:+.2f}%"
                                )
                                if qty > 0 and total_cost > 0:
                                    be_txt = f"${breakeven_price:.4f}" if breakeven_price else "(n/a)"
                                    tgt_txt = f"${target_price:.4f}" if target_price else "(n/a)"
                                    print(
                                        f"🧾 RADAR FINANCEIRO: CustoTotal=${total_cost:.2f} | Break-even={be_txt} | Alvo (+1% líquido)={tgt_txt}"
                                    )
                                    print(
                                        f"💰 Se vender AGORA (líquido): ${net_profit_now:+.2f} ({net_profit_pct:+.2f}%) | Taxa venda est.: -${(float(price) * qty * FEE_RATE):.3f}"
                                    )

                                bb_display = f"${bb_upper:.2f}" if bb_upper else "$0"
                                print(f"🔍 [DEBUG] Verificando saída: RSI={rsi:.1f} | Lucro={profit_pct:+.2f}% | BB_Upper={bb_display}")

                                with state_lock:
                                    should_sell, reason = check_exit_signal(pos, price, rsi, bb_upper, selected)

                                if should_sell:
                                    print(f"⚠️ [VENDA AUTORIZADA] {current_symbol}: {reason}")

                                    with state_lock:
                                        lab_state['current_rsi'] = rsi

                                    price_now = price
                                    if exchange:
                                        try:
                                            ticker = ex(exchange.fetch_ticker, current_symbol)
                                            price_now = ticker.get('last') or price
                                        except Exception:
                                            pass

                                    execute_real_trade('sell', price_now, current_symbol, reason=reason)

                                    print("⏳ Aguardando Binance estabilizar...")
                                    time.sleep(10)

                                    if ENABLE_GPT_TUNING:
                                        print("🤖 IA analisando resultado para ajustar estratégia...")
                                        analyze_market_with_gpt(current_symbol, price, rsi, bb_lower, 'sell')

                else:
                    with state_lock:
                        lab_state['status'] = 'Em Standby (Monitorando...) zzz'
                
                # Pequena pausa entre moedas para não estourar limite da API
                time.sleep(2)

            # 3. Atualiza saldo real e informações da conta (SEMPRE, para o dashboard)
            if exchange and API_KEY:
                try:
                    # Busca informações detalhadas da conta (UID, Permissões)
                    # Nota: private_get_account é específico da Binance
                    account_info = cached_private_get_account(ttl_s=10.0)
                    uid = account_info.get('uid', 'Não informado')
                    account_type = account_info.get('accountType', 'SPOT')
                    can_trade = account_info.get('canTrade', False)

                    # Se estiver bloqueado, imprime aviso
                    if not can_trade:
                        print(f"⚠️ CONTA BLOQUEADA PELA BINANCE. Resposta: {account_info.get('canTrade')}")

                    # Busca saldos
                    balance = cached_fetch_balance(ttl_s=3.0)

                    # Tenta pegar saldo em USDT ou BRL
                    usdt_total = balance.get('total', {}).get('USDT', 0.0)
                    usdt_free = balance.get('free', {}).get('USDT', 0.0)
                    brl_balance = balance.get('total', {}).get('BRL', 0.0)

                    # Filtra saldos > 0 para exibir
                    relevant_balances = {}
                    total_brl = 0.0

                    # Pega cotação USDT/BRL para converter
                    try:
                        usdt_brl_ticker = ex(exchange.fetch_ticker, 'USDT/BRL')
                        usdt_brl_price = usdt_brl_ticker['last']
                    except:
                        usdt_brl_price = 5.50  # Fallback

                    for asset, amount in balance.get('total', {}).items():
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
                                    ticker = ex(exchange.fetch_ticker, f'{asset}/USDT')
                                    asset_usdt_price = ticker['last']
                                    total_brl += amount * asset_usdt_price * usdt_brl_price
                                except:
                                    pass  # Ignora se não conseguir

                    with state_lock:
                        lab_state.setdefault('user_info', {})
                        lab_state['user_info']['uid'] = uid
                        lab_state['user_info']['type'] = account_type
                        lab_state['user_info']['can_trade'] = can_trade
                        lab_state['user_info']['balances'] = relevant_balances
                        lab_state['user_info']['total_brl'] = total_brl
                        lab_state['user_info']['usdt_brl_rate'] = usdt_brl_price
                        lab_state['user_info']['usdt_free'] = usdt_free
                        lab_state['user_info']['usdt_total'] = usdt_total

                        # SEMPRE usa USDT livre como saldo principal para trading
                        lab_state['real_balance'] = usdt_free
                        lab_state['brl_balance'] = brl_balance

                except Exception as e:
                    # Em caso de erro, loga para diagnóstico
                    print(f"⚠️ Erro ao atualizar saldo da conta: {e}")
                    # Tenta atualizar pelo menos o saldo básico
                    try:
                        balance = ex(exchange.fetch_balance)
                        usdt_free = balance.get('free', {}).get('USDT', 0.0)
                        usdt_total = balance.get('total', {}).get('USDT', 0.0)
                        brl_total = balance.get('total', {}).get('BRL', 0.0)
                        with state_lock:
                            lab_state['real_balance'] = usdt_free
                            lab_state.setdefault('user_info', {})
                            lab_state['user_info']['balances'] = {
                                'USDT': usdt_total,
                                'BRL': brl_total
                            }
                            lab_state['user_info']['usdt_free'] = usdt_free
                            lab_state['user_info']['usdt_total'] = usdt_total
                    except Exception as e2:
                        print(f"❌ Erro crítico ao buscar saldo: {e2}")

            # 4. Salva estado
            save_lab_data()
            
            # 5. Verifica se está na hora de enviar relatório via Telegram
            check_and_send_reports()

            # time.sleep(5)  # Aguarda 5 segundos (Removido pois já tem sleep no loop de moedas)

        except Exception as e:
            print(f"❌ Erro no loop: {e}")
            time.sleep(10)


@app.route('/api/status')
def api_status():
    """Retorna status geral do bot e carteira."""
    try:
        # Tenta pegar saldo atualizado do lab_state
        # O saldo real é atualizado no loop principal em lab_state['real_balance']
        total_balance = lab_state.get('real_balance', 0.0)
        
        # Tenta pegar saldo livre (USDT) se disponível, senão usa 0 ou total
        # Se 'wallet' não estiver sendo populado, assumimos 0 para free_usdt por enquanto
        usdt_balance = 0.0
        if 'wallet' in lab_state:
             usdt_balance = lab_state['wallet'].get('free_usdt', 0)
            
        return jsonify({
            'status': 'online',
            'total_balance': total_balance,
            'usdt_balance': usdt_balance,
            'uptime': 'Running', 
            'timestamp': now_iso()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai_context')
def api_ai_context():
    """
    🧠 ENDPOINT PARA IA (Telegram/OpenAI/Sandra)
    
    Retorna contexto completo com dados dinâmicos que a IA deve consultar.
    Garante que a IA NUNCA use valores fixos hardcoded.
    
    Uso:
        GET /api/ai_context
        
    Retorna:
        {
            "sentimento": "BEAR",
            "fear_greed_index": 25,
            "sentimento_descricao": "PÂNICO (oportunidade de compra)",
            "fator_juro_composto": 2.5,
            "saldo_atual": 250.00,
            "aposta_base_escalada": 27.50,
            "posicoes_abertas": {
                "BTC/USDT": {
                    "sl_pct": -2.5,
                    "sl_tipo": "DINÂMICO",
                    "tp_pct": 5.2,
                    "tp_tipo": "DINÂMICO"
                }
            },
            ...
        }
    """
    try:
        context = get_ai_context_data()
        return jsonify(context)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions')
def api_positions():
    """Retorna lista de posições ativas."""
    try:
        positions_list = []
        strategies = lab_state.get('strategies', {})
        market = lab_state.get('market_overview', {})
        
        def _append_pos(pos, strat_name):
            symbol = pos.get('symbol')
            if not symbol: return
            
            # Evita duplicatas
            for p in positions_list:
                if p['symbol'] == symbol and p['strategy'] == strat_name:
                    return

            entry_price = float(pos.get('entry_price', 0))
            current_price = 0.0
            if symbol in market:
                current_price = float(market[symbol].get('price', 0))
            
            profit_pct = 0.0
            if entry_price > 0 and current_price > 0:
                profit_pct = ((current_price - entry_price) / entry_price) * 100
            
            positions_list.append({
                'symbol': symbol,
                'entry_price': entry_price,
                'current_price': current_price,
                'profit_pct': profit_pct,
                'strategy': strat_name
            })

        # Itera sobre todas as estratégias
        for strat_name, strat_data in strategies.items():
            # 1. Verifica formato antigo (singular)
            single_pos = strat_data.get('position')
            if single_pos:
                _append_pos(single_pos, strat_name)
            
            # 2. Verifica formato novo (plural - dict)
            multi_pos = strat_data.get('positions', {})
            if isinstance(multi_pos, dict):
                for sym, pos in multi_pos.items():
                    _append_pos(pos, strat_name)
                
        return jsonify(positions_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist')
def api_watchlist():
    """Retorna dados da watchlist (RSI, Preço, Tendência)."""
    try:
        market = lab_state.get('market_overview', {})
        data = []
        
        for symbol in WATCHLIST:
            coin_data = market.get(symbol, {})
            if coin_data:
                data.append({
                    'symbol': symbol,
                    'price': coin_data.get('price', 0),
                    'rsi': coin_data.get('rsi', 0),
                    'trend': 'Alta' if coin_data.get('rsi', 50) > 50 else 'Baixa' # Simplificado
                })
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
def api_logs():
    """Retorna os últimos logs do sistema (simulado ou real)."""
    # Idealmente, ler de um arquivo de log ou lista em memória
    # Aqui vamos retornar uma lista fictícia ou os últimos eventos do lab_state se houver
    return jsonify({
        'logs': [
            {'time': now_sp().strftime('%H:%M:%S'), 'level': 'INFO', 'message': 'Sistema operando normalmente.'},
            {'time': now_sp().strftime('%H:%M:%S'), 'level': 'INFO', 'message': 'Monitorando 10 pares de moedas.'}
        ]
    })

@app.route('/api/chart/<symbol_safe>')
def api_chart(symbol_safe):
    """Retorna dados de candles para o gráfico."""
    try:
        symbol = symbol_safe.replace('_', '/')
        # Aqui você precisaria ter o histórico de candles salvo ou buscar na hora
        # Como exemplo, vamos retornar erro ou dados vazios se não tiver cache
        # Se você tiver o 'market_overview' com histórico, use-o.
        
        # Mock de dados para teste visual (já que não temos histórico persistido fácil aqui)
        # Em produção, conecte com ccxt.fetch_ohlcv
        return jsonify({'candles': []}) 
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/command/<cmd>', methods=['POST'])
def api_command(cmd):
    """Executa comandos manuais."""
    _require_api_token_if_configured()
    print(f"Comando recebido: {cmd}")
    db_record_event('command', f"Comando manual: {cmd}", data={'remote_addr': request.remote_addr})
    try:
        if cmd == 'report':
            # Relatório de mercado via Telegram
            send_daily_report()
            return jsonify({'status': 'ok', 'command': cmd, 'message': 'Relatório Telegram disparado'})

        if cmd == 'daily_email':
            ok, msg = send_daily_email_report_now()
            return jsonify({'status': 'ok' if ok else 'error', 'command': cmd, 'message': msg}), (200 if ok else 400)

        # Placeholder para outras ações
        return jsonify({'status': 'executed', 'command': cmd})
    except Exception as e:
        return jsonify({'status': 'error', 'command': cmd, 'error': str(e)}), 500

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
        snap = get_public_snapshot()
        selected = snap.get('selected_strategy', 'aggressive')
        trades = (snap.get('strategies', {}).get(selected, {}) or {}).get('trades', [])
        
        def _is_sell_trade(t: dict) -> bool:
            side = t.get('side')
            if side:
                return side == 'sell'
            legacy_type = (t.get('type') or '').upper()
            return legacy_type.startswith('SELL')

        # Estatísticas básicas (SOMENTE VENDAS)
        sell_trades_list = [t for t in trades if _is_sell_trade(t)]
        total_trades = len(sell_trades_list)
        
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
        
        # Calcula métricas (SOMENTE VENDAS - BUY não conta)
        sell_trades = sell_trades_list

        def _to_float(v, default=0.0) -> float:
            try:
                return float(v)
            except Exception:
                return float(default)

        def _profit_usdt(t: dict) -> float:
            if t.get('net_profit_usdt') is not None:
                return _to_float(t.get('net_profit_usdt'), 0.0)
            return 0.0

        def _profit_pct(t: dict) -> float:
            if t.get('net_profit_pct') is not None:
                return _to_float(t.get('net_profit_pct'), 0.0)
            return _to_float(t.get('profit_pct', 0.0), 0.0)

        winning_trades = []
        losing_trades = []
        accumulated = []
        cumulative_usdt = 0.0

        profits_usdt = []
        profits_pct = []

        for trade in sell_trades:
            p_usdt = _profit_usdt(trade)
            p_pct = _profit_pct(trade)
            profits_usdt.append(p_usdt)
            profits_pct.append(p_pct)

            if p_usdt > 0:
                winning_trades.append(trade)
            else:
                losing_trades.append(trade)

            cumulative_usdt += p_usdt
            accumulated.append({
                'time': trade.get('exit_time', trade.get('time', '')),
                'profit': round(cumulative_usdt, 4)
            })

        total_profit_pct = sum(profits_pct)
        best_trade = max(profits_pct) if profits_pct else 0
        worst_trade = min(profits_pct) if profits_pct else 0
        avg_trade = total_profit_pct / total_trades if total_trades > 0 else 0
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0

        total_profit_usdt = sum(profits_usdt)
        usdt_brl = _to_float((snap.get('user_info', {}) or {}).get('usdt_brl_rate', 0.0), 0.0)
        total_profit_brl = (total_profit_usdt * usdt_brl) if usdt_brl > 0 else 0.0
        
        # Prepara trades para exibição (últimas 50 vendas)
        trades_display = []
        for t in sell_trades[-50:]:
            trades_display.append({
                'symbol': t.get('symbol', ''),
                'type': t.get('action', t.get('type', '')),
                'entry_price': t.get('entry_price', 0),
                'exit_price': t.get('exit_price', 0),
                'profit_pct': t.get('net_profit_pct', t.get('profit_pct', 0)),
                'profit_usdt': t.get('net_profit_usdt', 0),
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


@app.route('/api/send_report', methods=['POST'])
def send_report_now():
    """Envia relatório imediatamente via Telegram."""
    try:
        _require_api_token_if_configured()
        send_daily_report()
        return jsonify({'success': True, 'message': 'Relatório enviado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/report')
def get_report():
    """Retorna relatório em formato texto para visualização."""
    try:
        report = generate_market_report()
        return jsonify({'report': report})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Retorna estado completo do laboratório."""
    _require_api_token_if_configured()
    return jsonify(get_public_snapshot())


@app.route('/api/logs')
def get_logs():
    """Retorna as últimas linhas do log do servidor."""
    try:
        log_file = 'server.log'
        if not os.path.exists(log_file):
            return jsonify({'logs': []})
        
        # Lê as últimas 50 linhas
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            last_lines = lines[-50:]
            
        return jsonify({'logs': [l.strip() for l in last_lines]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/position')
def get_position():
    """Retorna informações da posição ativa (compatível com multi-posições)."""
    try:
        with state_lock:
            selected = lab_state.get('selected_strategy')
            strategy = lab_state.get('strategies', {}).get(selected, {}) or {}
            positions_dict = strategy.get('positions') if isinstance(strategy.get('positions'), dict) else {}
            position = None
            count = 0

            if positions_dict:
                count = len(positions_dict)
                first_symbol = next(iter(positions_dict))
                position = copy.deepcopy(positions_dict.get(first_symbol))
            else:
                position = copy.deepcopy(strategy.get('position'))
            cached_price = lab_state.get('current_price')
            is_drawdown = bool(GLOBAL_STATS.get('drawdown_mode', False))
        
        if not position:
            return jsonify({'has_position': False})
        
        symbol = position.get('symbol', SYMBOL)
        entry_price = position.get('entry_price', 0)
        qty = position.get('qty', 0)
        entry_time = position.get('entry_time', '')
        
        # Busca preço atual
        current_price = cached_price if cached_price is not None else entry_price
        
        # Tenta pegar preço atualizado da API
        if exchange:
            try:
                ticker = ex(exchange.fetch_ticker, symbol)
                current_price = ticker['last']
            except:
                pass
        
        # Calcula lucro/prejuízo
        profit_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        profit_value = (current_price - entry_price) * qty
        
        # Calcula metas (CONFIGURAÇÃO SANDRA MODE REAL)
        take_profit_price = entry_price * (1 + SANDRA["TP_SLOW"] / 100)  # TP_SLOW = 5%
        stop_pct = SANDRA["STOP_DRAWDOWN"] if is_drawdown else SANDRA["STOP_BASE"]  # -2% ou -3%
        stop_loss_price = entry_price * (1 + stop_pct / 100)
        
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
            'count': count,
            'take_profit_price': take_profit_price,
            'stop_loss_price': stop_loss_price,
            'position_value': position_value,
            'entry_value': entry_value,
            'distance_to_tp': ((take_profit_price - current_price) / current_price) * 100,
            'distance_to_sl': ((current_price - stop_loss_price) / current_price) * 100
        })
        
    except Exception as e:
        return jsonify({'has_position': False, 'error': str(e)})


@app.route('/api/clear-position', methods=['POST'])
def clear_position():
    """Limpa posição manualmente (para emergências como dust)."""
    _require_api_token_if_configured()
    try:
        with state_lock:
            selected = lab_state['selected_strategy']
            strategy = lab_state['strategies'][selected]

            old_positions = dict(strategy.get('positions') or {}) if isinstance(strategy.get('positions'), dict) else {}
            old_position = strategy.get('position')

            strategy['positions'] = {}
            strategy['position'] = None

        save_lab_data()
        
        if old_positions or old_position:
            count = len(old_positions) if old_positions else 1
            print(f"🧹 POSIÇÕES LIMPAS MANUALMENTE: {count}")
            send_telegram_message(f"🧹 *POSIÇÕES LIMPAS MANUALMENTE*\n\nTotal: {count}")
            return jsonify({'success': True, 'message': f'Posições limpas: {count}'})
        else:
            return jsonify({'success': True, 'message': 'Nenhuma posição ativa para limpar'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    """Retorna dados de velas e indicadores para gráfico."""
    try:
        # Converte símbolo (BTC-USDT -> BTC/USDT)
        symbol_clean = symbol.replace('-', '/')
        
        if not exchange:
            return jsonify({'error': 'Exchange não conectada'}), 500
        
        # Busca últimas 100 velas de 5 minutos
        # USANDO REQUESTS DIRETAMENTE (API PÚBLICA) PARA EVITAR ERRO DE CHAVE
        try:
            url = 'https://api.binance.com/api/v3/klines'
            params = {'symbol': symbol_clean.replace('/', ''), 'interval': '5m', 'limit': 100}
            raw_data = _http_get_json(url, params=params, timeout=10, retries=2)
            # Converte formato da API (strings) para formato CCXT (floats)
            ohlcv = []
            for row in raw_data:
                ohlcv.append([
                    row[0],          # Time
                    float(row[1]),   # Open
                    float(row[2]),   # High
                    float(row[3]),   # Low
                    float(row[4]),   # Close
                    float(row[5])    # Volume
                ])
        except Exception as e:
            print(f"❌ Erro ao buscar dados públicos para {symbol_clean}: {e}")
            raise e
        
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
        logging.error(f"Erro em get_chart_data: {e}")
        logging.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist')
def get_watchlist():
    """Retorna lista de moedas monitoradas."""
    snapshot = get_public_snapshot()
    return jsonify({
        'watchlist': WATCHLIST,
        'market_overview': snapshot.get('market_overview', {})
    })


@app.route('/api/select_strategy', methods=['POST'])
def select_strategy():
    """Seleciona qual estratégia usar no modo real."""
    data = request.json
    strategy_key = data.get('strategy')

    if strategy_key in lab_state['strategies']:
        with state_lock:
            lab_state['selected_strategy'] = strategy_key
        save_lab_data()
        return jsonify({'success': True, 'selected': strategy_key})

    return jsonify({'success': False, 'error': 'Estratégia inválida'}), 400


@app.route('/api/toggle_live', methods=['POST'])
def toggle_live():
    """Liga/Desliga o modo real."""
    _require_api_token_if_configured()
    data = request.json
    is_live = data.get('is_live', False)

    if is_live and (not API_KEY or not SECRET):
        return jsonify({'success': False, 'error': 'Chaves API não configuradas'}), 400

    with state_lock:
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
    _require_api_token_if_configured()
    data = request.json
    running = data.get('running', False)
    
    with state_lock:
        lab_state['running'] = running
    save_lab_data()
    
    print(f"🤖 ROBÔ {'LIGADO' if running else 'DESLIGADO'}")
    return jsonify({'success': True, 'running': running})


@app.route('/api/convert_brl', methods=['POST'])
def convert_brl_endpoint():
    """🔄 Converte BRL para USDT manualmente."""
    if not exchange or not API_KEY or not SECRET:
        return jsonify({'success': False, 'error': '❌ Chaves API não configuradas!'}), 400
    
    try:
        # Busca saldos atuais
        balance = ex(exchange.fetch_balance)
        brl_before = balance['total'].get('BRL', 0.0)
        usdt_before = balance['total'].get('USDT', 0.0)
        
        if brl_before < 10:
            return jsonify({'success': False, 'error': f'Saldo BRL muito baixo: R${brl_before:.2f}'}), 400
        
        # Converte
        new_usdt = convert_brl_to_usdt(min_brl=10)
        
        return jsonify({
            'success': True,
            'message': f'✅ Conversão realizada!',
            'brl_before': brl_before,
            'usdt_before': usdt_before,
            'usdt_after': new_usdt
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/force_buy', methods=['POST'])
def force_buy():
    """⚡ COMPRA FORÇADA - Ignora indicadores, testa conexão com Binance."""
    _require_api_token_if_configured()
    if not exchange or not API_KEY or not SECRET:
        return jsonify({'success': False, 'error': '❌ Chaves API não configuradas!'}), 400
    
    data = request.json
    symbol = data.get('symbol', 'BTC/USDT')  # Padrão BTC/USDT
    amount_usd = 11.0  # Valor mínimo para teste
    
    try:
        # Regra Sandra: BTC sangrando 3 dias = não compra em lugar nenhum
        if btc_bleeding_3days_cached():
            return jsonify({'success': False, 'error': '🩸 BTC sangrando 3 dias. Sandra NÃO compra até voltar.'}), 400

        # Sandra: até 3 posições
        with state_lock:
            strategy_key = lab_state['selected_strategy']
            strategy = lab_state['strategies'][strategy_key]
            strategy.setdefault('positions', {})
            if len(strategy.get('positions') or {}) >= 3:
                return jsonify({'success': False, 'error': '📍 Limite de 3 posições atingido. Sandra não abre a 4ª.'}), 400

        print(f"{'='*60}")
        print(f"⚡ COMPRA FORÇADA INICIADA - {symbol}")
        print(f"{'='*60}")
        
        # Busca preço atual
        ticker = ex(exchange.fetch_ticker, symbol)
        current_price = ticker['last']
        
        # Calcula quantidade
        qty = amount_usd / current_price
        
        # Executa ordem de mercado
        order = ex(exchange.create_market_buy_order, symbol, qty)
        
        print(f"✅ ORDEM EXECUTADA!")
        print(f"   ID: {order['id']}")
        print(f"   Preço: ${order.get('average', current_price):.2f}")
        print(f"   Quantidade: {order['filled']}")
        
        # Notifica no Telegram
        msg = f"⚡ *COMPRA FORÇADA (TESTE)*\n\n🪙 Moeda: {symbol}\n💰 Preço: ${current_price:.2f}\n📦 Qtd: {order['filled']}\n🆔 Order ID: {order['id']}"
        send_telegram_message(msg)
        
        # Registra na estratégia ativa (padrão persistente)
        with state_lock:
            trade = {
                'timestamp': now_iso(),
                'side': 'buy',
                'symbol': symbol,
                'price': order.get('average', current_price),
                'qty': order['filled'],
                'fees': float(order.get('cost', amount_usd)) * FEE_RATE,
                'mode': 'REAL (TESTE)',
                'rsi': lab_state.get('indicators', {}).get('rsi', 0.0),

                'time': now_sp().strftime('%H:%M:%S'),
                'type': f'⚡ FORCE BUY ({symbol})',
                'order_id': order.get('id', ''),
                'profit_pct': 0,
            }
            strategy_key = lab_state['selected_strategy']
            lab_state['strategies'][strategy_key]['trades'].append(trade)

            buy_price = order.get('average', current_price)
            buy_total = float(order.get('cost', buy_price * float(order['filled'])))
            pos_obj = {
                'symbol': symbol,
                'entry_price': buy_price,
                'qty': order['filled'],
                'entry_time': now_iso(),
                'highest_price': buy_price,
                'trail_active': False,
                'entry_cost_usdt': buy_total,
                'entry_fee_usdt': buy_total * FEE_RATE,
            }
            st = lab_state['strategies'][strategy_key]
            st.setdefault('positions', {})
            st['positions'][symbol] = pos_obj
            # Compatibilidade: aponta para a "posição principal" (primeira inserida)
            first_symbol = next(iter(st['positions'])) if st['positions'] else None
            st['position'] = st['positions'].get(first_symbol) if first_symbol else None
            # Adiciona o cooldown para a moeda comprada
            lab_state.setdefault('symbol_cooldowns', {})[symbol] = time.time()
            
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


@app.route('/api/close_position', methods=['POST'])
def close_position():
    """⚡ VENDA FORÇADA - Vende a posição atual a mercado (Alias para force_sell no frontend)."""
    _require_api_token_if_configured()
    if not exchange:
        return jsonify({'success': False, 'error': 'Exchange não conectada'}), 400

    try:
        with state_lock:
            selected = lab_state['selected_strategy']
            strategy = lab_state['strategies'][selected]
            strategy.setdefault('positions', {})
            # Compatibilidade: tenta usar a posição principal; senão, pega a primeira do dict
            position = strategy.get('position')
            if not position and strategy.get('positions'):
                first_symbol = next(iter(strategy['positions']))
                position = strategy['positions'].get(first_symbol)

            if not position:
                return jsonify({'success': False, 'error': 'Nenhuma posição aberta para vender.'}), 400

            symbol = position.get('symbol')
            qty = float(position.get('qty', 0) or 0)

        print(f"⚡ VENDA FORÇADA INICIADA - {symbol} Qty: {qty}")
        
        # Reusa o executor multi-posições (mantém consistência com logs/telegram/charts)
        price_now = None
        try:
            ticker = ex(exchange.fetch_ticker, symbol)
            price_now = ticker.get('last')
        except Exception:
            price_now = None

        ok = execute_real_trade('sell', price_now or 0.0, symbol, reason='FORCE_SELL')
        if not ok:
            return jsonify({'success': False, 'error': 'Falha ao executar venda forçada (ver logs).'}), 500

        return jsonify({'success': True, 'message': 'Venda executada com sucesso!'})

    except Exception as e:
        print(f"❌ Erro na venda forçada: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# --- TELEGRAM BOT HANDLERS ---

async def telegram_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Modo Sandra - Ativo!*\n\n"
        "Olá! Sou sua guarda-costas com cérebro de trader. "
        "Vou operar com sabedoria: ganhar devagar, perder menos, e fazer repique gordo quando der!\n\n"
        "💡 *Como posso te ajudar?*\n"
        "• Use /ajuda para ver todos os comandos\n"
        "• Use /status para ver o que estou analisando\n"
        "• Use /relatorio para análise completa do mercado\n"
        "• Ou apenas converse comigo digitando qualquer mensagem!\n\n"
        "📊 Modo: Apostas variáveis ($11/$22/$33)\n"
        "🛡️ Proteção: Trailing Stop ativo\n"
        "💰 Cálculo: Lucro líquido com taxas reais",
        parse_mode='Markdown'
    )

async def telegram_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *BOT MODO SANDRA - COMANDOS*\n\n"
        "📊 *Informações do Sistema:*\n"
        "/status - O que estou analisando agora\n"
        "/saldo - Seu saldo em BRL e USDT\n"
        "/posicao - Posição principal (compatibilidade)\n"
        "/moedas - Relatório Profissional (Carteira + Radar)\n"
        "/relatorio - Relatório completo do mercado\n"
        "/grafico - Gráfico sob demanda (moeda atual)\n\n"
        "⚙️ *Controle:*\n"
        "/comprar [MOEDA] - Força compra imediata (Ex: /comprar XRP)\n"
        "/converter - Converte BRL→USDT (quando faltar saldo)\n"
        "/ligar - Liga o bot automático\n"
        "/desligar - Desliga o bot automático\n\n"
        "💬 *Conversa com IA:*\n"
        "/ia - Mostra parâmetros (ou /ia reset)\n"
        "Envie qualquer mensagem para conversar comigo.\n\n"
        "🔭 *Caçador + Juiz (automático):*\n"
        "• Caçador adiciona moedas trending (CoinGecko) que existirem na Binance\n"
        "• Juiz (IA) filtra projetos suspeitos antes de entrar no radar\n\n"
        "🧾 *Financeiro:*\n"
        "• Radar Financeiro no log: break-even e alvo líquido por posição\n"
        "• Venda por RSI alto só executa se lucro cobrir taxas (LUCRO_MINIMO_TAXAS)\n\n"
        "🎯 *Modo Sandra Ativo:*\n"
        "• Apostas: $11 (normal), $22 (forte), $33 (ouro)\n"
        "• Trailing Stop: Deixa lucro correr acima de 5%\n"
        "• Proteção: Reduz aposta se perder 10%\n"
        "• Taxas: Calcula lucro líquido real (0.2%)",
        parse_mode='Markdown'
    )

async def telegram_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        snap = get_public_snapshot()
        msg = "📊 *STATUS DO MERCADO*\n\n"
        msg += f"🪙 *Moeda:* {snap.get('current_symbol', '---')}\n"
        msg += f"💰 *Preço:* ${float(snap.get('current_price', 0.0) or 0.0):.2f}\n"
        indicators = snap.get('indicators', {}) or {}
        msg += f"📉 *RSI:* {float(indicators.get('rsi', 0.0) or 0.0):.2f}\n"
        msg += f"🛡️ *Bandas:* {float(indicators.get('bb_lower', 0.0) or 0.0):.2f}\n\n"
        
        msg += f"⚙️ *Configuração:*\n"
        msg += f"Estratégia: {snap.get('selected_strategy', 'aggressive')}\n"
        msg += f"Modo: Trading Real 💰\n"
        msg += f"Status: {snap.get('status', '')}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar status: {str(e)}")

async def telegram_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        snap = get_public_snapshot()
        balances = (snap.get('user_info', {}) or {}).get('balances', {}) or {}
        msg = "💰 *SEU SALDO*\n\n"
        
        # Se não tem saldo no cache, busca direto da API
        if not balances:
            try:
                balance = cached_fetch_balance(ttl_s=5.0)
                balances = {}
                for asset, amount in balance['total'].items():
                    if float(amount) > 0:
                        balances[asset] = float(amount)
            except: pass

        if not balances:
            msg += "⚠️ Não foi possível ler o saldo da Binance."
        else:
            usdt = balances.get('USDT', 0.0)
            brl = balances.get('BRL', 0.0)
            
            msg += f"💵 *USDT:* ${usdt:.2f}\n"
            msg += f"🇧🇷 *BRL:* R${brl:.2f}\n\n"
            
            msg += "🪙 *Outras Moedas:*\n"
            for coin, amount in balances.items():
                if coin not in ['USDT', 'BRL'] and float(amount) > 0:
                    # Filtra dust
                    if float(amount) > 0.0001: 
                        msg += f"• *{coin}:* {amount:.4f}\n"
            
            # Total em BRL
            total_brl = float((snap.get('user_info', {}) or {}).get('total_brl', 0) or 0)
            if total_brl > 0:
                msg += f"\n📊 *Total em BRL:* R${total_brl:.2f}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao buscar saldo: {str(e)}")

async def telegram_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra posição aberta atual."""
    try:
        snap = get_public_snapshot()
        strategy_key = snap.get('selected_strategy', 'aggressive')
        position = (snap.get('strategies', {}) or {}).get(strategy_key, {}).get('position')
        
        if not position:
            await update.message.reply_text("📍 *Nenhuma posição aberta no momento.*\n\nO bot está aguardando oportunidade de compra.", parse_mode='Markdown')
            return
            
        symbol = position.get('symbol')
        entry_price = float(position.get('entry_price', 0))
        qty = float(position.get('qty', 0))
        entry_time = position.get('entry_time', '')
        
        current_price = float(snap.get('current_price', 0) or entry_price)
        
        # Calcula lucro atual
        gross_val = current_price * qty
        cost_val = entry_price * qty
        profit_usd = gross_val - cost_val
        profit_pct = (profit_usd / cost_val) * 100 if cost_val > 0 else 0
        
        emoji = "🟢" if profit_usd >= 0 else "🔴"
        
        msg = f"{emoji} *POSIÇÃO ABERTA* | {symbol}\n\n"
        msg += f"💵 *Entrada:* ${entry_price:.4f}\n"
        msg += f"📊 *Atual:* ${current_price:.4f}\n"
        msg += f"📦 *Quantidade:* {qty:.4f}\n"
        msg += f"{emoji} *Lucro:* {profit_pct:+.2f}% (${profit_usd:+.2f})\n"
        msg += f"🕐 *Desde:* {entry_time[:16] if len(entry_time) > 16 else entry_time}"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

async def telegram_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    RELATÓRIO VISUAL: Separa Carteira (Dinheiro) de Radar (Oportunidades).
    """
    try:
        # 1. Cabeçalho
        msg = "🖥️ *SANDRA AI - MONITORAMENTO*\n"
        msg += f"🕒 {now_sp().strftime('%H:%M')}\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Coleta posições de todas as estratégias
        strategies = lab_state.get('strategies', {})
        portfolio = []
        
        for strat_name, strat_data in strategies.items():
            # Formato antigo
            pos = strat_data.get('position')
            if pos: portfolio.append(pos)
            # Formato novo
            positions = strat_data.get('positions', {})
            if isinstance(positions, dict):
                for p in positions.values():
                    portfolio.append(p)

        total_investido = 0
        total_liquido_agora = 0
        tem_posicao = False

        # === SEÇÃO 1: SUAS POSIÇÕES (Onde seu dinheiro está) ===
        if portfolio:
            msg += "💼 *SUA CARTEIRA (Ativos)*\n"
            for data in portfolio:
                tem_posicao = True
                symbol = data.get('symbol')
                qty = float(data.get('qty', 0))
                buy_price = float(data.get('entry_price', 0))
                
                try:
                    # Tenta pegar preço atual do market_overview (mais rápido) ou exchange
                    market_data = lab_state.get('market_overview', {}).get(symbol, {})
                    curr_price = float(market_data.get('price', 0))
                    
                    if curr_price == 0:
                         # Fallback se não tiver no market overview
                         ticker = ex(exchange.fetch_ticker, symbol)
                         curr_price = float(ticker['last'])

                    # Conta: (Preço Agora * Qtd) - (Preço Pago * Qtd) - Taxas 0.2%
                    custo = qty * buy_price
                    bruto = qty * curr_price
                    taxas = bruto * 0.002 # Estimativa
                    liquido = bruto - custo - taxas
                    pct = (liquido / custo) * 100 if custo > 0 else 0
                    
                    icon = "✅" if liquido > 0 else "🔻"
                    
                    msg += f"📦 *{symbol}* {icon}\n"
                    msg += f"   ├ 📥 Pagou: ${buy_price:.4f}\n"
                    msg += f"   ├ 🏷️ Atual: ${curr_price:.4f}\n"
                    msg += f"   └ 💸 *Líquido: ${liquido:+.2f} ({pct:+.2f}%)*\n"
                    
                    total_investido += custo
                    total_liquido_agora += liquido
                except Exception as e:
                    msg += f"📦 {symbol}: Erro ao atualizar.\n"
            msg += "\n"

        # === SEÇÃO 2: RADAR (O que ficar de olho) ===
        msg += "📡 *RADAR DE MERCADO*\n"
        
        oportunidades = []
        resto = []
        
        market = lab_state.get('market_overview', {})
        portfolio_symbols = [p.get('symbol') for p in portfolio]

        for symbol in WATCHLIST:
            if symbol in portfolio_symbols: continue 
            
            try:
                # Usa dados do market_overview que já tem RSI e Price
                data = market.get(symbol)
                if not data: continue

                price = float(data.get('price', 0))
                rsi = float(data.get('rsi', 0))
                
                line = f"{symbol}: ${price:.2f} | RSI: *{rsi:.1f}*"
                
                if rsi <= 32:
                    oportunidades.append(f"❄️ {line} (BARATO!)")
                elif rsi >= 70:
                    oportunidades.append(f"🔥 {line} (CARO)")
                else:
                    resto.append(f"⚪ {line}")
            except:
                continue
                
        # Mostra primeiro as oportunidades
        for line in oportunidades:
            msg += line + "\n"
            
        # Mostra o resto (limitado a 5)
        for i, line in enumerate(resto):
            if i >= 5: break
            msg += line + "\n"

        # === RODAPÉ FINANCEIRO ===
        if tem_posicao:
            msg += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            pnl_geral = (total_liquido_agora / total_investido * 100) if total_investido > 0 else 0
            msg += f"💰 *RESULTADO HOJE:*\n"
            msg += f"Investido: ${total_investido:.2f}\n"
            msg += f"Líquido:   *${total_liquido_agora:+.2f} ({pnl_geral:+.2f}%)*"

        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro no relatório: {str(e)}")

async def telegram_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia relatório completo."""
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        report = generate_market_report()
        await update.message.reply_text(report, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

async def telegram_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Força compra de uma moeda específica."""
    try:
        # Pega o argumento (moeda)
        args = context.args
        if not args:
            await update.message.reply_text("⚠️ Use: /comprar XRP (ou BTC, ETH, etc)")
            return
        
        coin = args[0].upper()
        symbol = f"{coin}/USDT"
        
        # Verifica se é uma moeda válida
        if symbol not in WATCHLIST:
            await update.message.reply_text(f"⚠️ Moeda {coin} não está na lista de monitoramento.")
            return
            
        await update.message.reply_text(f"⏳ Analisando compra forçada de {symbol}...")
        
        # Executa compra real
        price = get_price(symbol)
        if not price:
            await update.message.reply_text("❌ Erro ao obter preço.")
            return

        # Define valor da aposta (usa o padrão Sandra)
        invest_amount = get_sandra_bet_size()
        
        # Verifica se pode comprar (regras básicas)
        # Ignora cooldown na compra forçada? Talvez não. Vamos tentar executar.
        # Mas execute_real_trade tem cooldown.
        # Vamos avisar que estamos tentando.
        
        ok = execute_real_trade('buy', price, symbol, amount_usdt=invest_amount)
        if ok:
            await update.message.reply_text(f"✅ Compra enviada no padrão Sandra (${invest_amount:.0f}).")
        else:
            await update.message.reply_text("❌ Compra não executada (mínimo/saldo/proteção/cooldown).")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Erro na compra: {str(e)}")


async def telegram_convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Converte BRL para USDT."""
    try:
        await update.message.reply_text("🔄 Convertendo BRL para USDT...")
        
        # Executa em thread separada para não bloquear o bot
        result = await asyncio.to_thread(convert_brl_to_usdt, 10)
        
        if result > 0:
            await update.message.reply_text(f"✅ Conversão concluída!\n\n💰 Saldo USDT: ${result:.2f}")
        else:
            await update.message.reply_text("❌ Não foi possível converter. Verifique seu saldo BRL.")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")

async def telegram_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia gráfico da moeda atual sob demanda."""
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_photo')
        
        with state_lock:
            symbol = lab_state.get('current_symbol', 'BTC/USDT')
        
        chart_buf = generate_chart_image(symbol)
        if chart_buf:
            await update.message.reply_photo(photo=chart_buf, caption=f"📊 Gráfico atual: {symbol}")
        else:
            await update.message.reply_text("❌ Não foi possível gerar o gráfico.")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar gráfico: {e}")

async def telegram_start_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Liga o bot automático."""
    with state_lock:
        lab_state['running'] = True
        save_lab_data()
    await update.message.reply_text("🟢 Bot LIGADO! Agora monitorando o mercado e executando trades automaticamente.")

async def telegram_stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desliga o bot automático."""
    with state_lock:
        lab_state['running'] = False
        save_lab_data()
    await update.message.reply_text("🔴 Bot DESLIGADO! Use /ligar para reativar.")


async def telegram_ia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra parâmetros reais do Sandra Mode (SANDRA) ou reseta para padrão."""

    args = context.args if context.args else []

    if args and args[0].lower() == 'reset':
        with state_lock:
            # Reseta apenas o que é ajustável na prática (o resto é regra fixa)
            SANDRA["ENTRY_RSI"] = 35
            SANDRA["ENTRY_TOL"] = 0.01
            SANDRA["STOP_BASE"] = -3.0
            SANDRA["STOP_DRAWDOWN"] = -10.0
            SANDRA["TP_SLOW"] = 5.0
            SANDRA["TRAIL_FAST"] = 1.5
            SANDRA["MAX_BET"] = 33.0
        await update.message.reply_text("✅ Parâmetros da IA resetados para o padrão Sandra.")
        return

    await update.message.reply_text(
        "🧠 *Cérebro da Sandra*\n\n"
        "Aqui estão os parâmetros que estou usando para decidir:\n\n"
        f"🎯 *Entrada:* RSI < {SANDRA['ENTRY_RSI']} (Tol: {SANDRA['ENTRY_TOL']*100:.1f}%)\n"
        f"🛑 *Stop Loss:* {SANDRA['STOP_BASE']}%\n"
        f"🛡️ *Drawdown:* {SANDRA['STOP_DRAWDOWN']}%\n"
        f"💰 *Take Profit:* {SANDRA['TP_SLOW']}%\n"
        f"🏃 *Trailing:* {SANDRA['TRAIL_FAST']}%\n"
        f"🎲 *Aposta Máx:* ${SANDRA['MAX_BET']:.0f}\n\n"
        "Use `/ia reset` para voltar ao padrão.",
        parse_mode='Markdown'
    )

def get_database_summary():
    """Lê o histórico do DB e retorna resumo para a IA."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Tenta ler do histórico (se houver)
        cursor.execute('SELECT COUNT(*), SUM(profit_usdt) FROM trade_history')
        row = cursor.fetchone()
        total_trades = row[0] if row else 0
        total_profit = row[1] if row and row[1] else 0.0
        
        # Se não tiver histórico na tabela, tenta ler do JSON state
        if total_trades == 0:
            cursor.execute('SELECT value FROM system_state WHERE key = ?', ('lab_state',))
            row_state = cursor.fetchone()
            if row_state:
                data = json.loads(row_state[0])
                pnl = data.get('pnl', {})
                total_profit = pnl.get('total_net', 0.0)
                # Estima trades (não perfeito, mas serve)
                total_trades = len(data.get('strategies', {}).get('aggressive', {}).get('trades', []))

        conn.close()
        
        return (
            f"RESUMO DO BANCO DE DADOS:\n"
            f"- Lucro Total Acumulado: ${total_profit:.2f}\n"
            f"- Total de Trades Registrados: {total_trades}\n"
        )
    except Exception as e:
        return f"Erro ao ler banco de dados: {e}"


def generate_profit_scenarios(entry_price: float, qty: float, total_cost_usdt: float, fee_rate: float = 0.001):
    """Gera tabela de cenários futuros (lucro líquido estimado já com taxa de venda).

    total_cost_usdt deve incluir: custo bruto da compra + taxa de compra paga.
    """
    try:
        entry_price = float(entry_price or 0.0)
        qty = float(qty or 0.0)
        total_cost_usdt = float(total_cost_usdt or 0.0)

        if entry_price <= 0 or qty <= 0 or total_cost_usdt <= 0:
            return ""

        targets = [0.8, 1.5, 3.0, 5.0]
        out = "📊 *CENÁRIOS DE VENDA FUTURA (com taxas):*\n"
        for pct in targets:
            target_price = entry_price * (1 + pct / 100)
            gross_sell = target_price * qty
            sell_fee = gross_sell * fee_rate
            net_sell = gross_sell - sell_fee
            net_profit = net_sell - total_cost_usdt
            out += f"🎯 Se subir {pct}% (Preço ${target_price:.4f}): *${net_profit:+.2f}*\n"
        return out
    except Exception:
        return ""


def get_position_context_string():
    """Gera o contexto REAL de posições + cenários para a IA (multi-posições)."""
    try:
        with state_lock:
            selected = lab_state.get('selected_strategy', 'aggressive')
            strategy = lab_state['strategies'][selected]
            positions = strategy.get('positions') if isinstance(strategy.get('positions'), dict) else {}
            legacy_pos = strategy.get('position') if isinstance(strategy.get('position'), dict) else None
            market_overview = lab_state.get('market_overview', {}) or {}

        # Compatibilidade: se ainda existir position antiga, considera como uma posição
        if not positions and legacy_pos:
            sym = legacy_pos.get('symbol')
            positions = {sym or 'UNKNOWN': legacy_pos}

        if not positions:
            return "STATUS: Nenhuma posição aberta. Caixa 100% USDT."

        fee_rate = float(FEE_RATE)
        target_net_pct = 0.01  # +1% líquido sobre o custo total (educacional)
        report = "⚠️ *DADOS DAS POSIÇÕES ABERTAS (com cenários):*\n\n"

        for sym, pos in positions.items():
            symbol = pos.get('symbol') or sym
            entry_price = float(pos.get('entry_price', 0) or 0)
            qty = float(pos.get('qty', 0) or 0)
            entry_cost = float(pos.get('entry_cost_usdt', entry_price * qty) or 0)
            entry_fee = float(pos.get('entry_fee_usdt', 0.0) or 0.0)
            total_cost = entry_cost + entry_fee

            # Preço atual: preferir market_overview por símbolo
            current_price = None
            try:
                current_price = (market_overview.get(symbol, {}) or {}).get('price')
            except Exception:
                current_price = None
            if current_price is None:
                current_price = entry_price
            current_price = float(current_price or entry_price)

            gross_now = current_price * qty
            sell_fee_now = gross_now * fee_rate
            net_sell_now = gross_now - sell_fee_now
            net_profit_now = net_sell_now - total_cost
            net_profit_pct = (net_profit_now / total_cost) * 100 if total_cost > 0 else 0.0

            denom = qty * (1 - fee_rate)
            breakeven_price = (total_cost / denom) if denom > 0 else None
            target_price = (total_cost * (1 + target_net_pct) / denom) if denom > 0 else None

            report += f"🪙 *{symbol}*\n"
            report += f"- Compra: ${entry_price:.4f} | Agora: ${current_price:.4f}\n"
            if breakeven_price and target_price:
                report += f"- Break-even (com taxas): ${breakeven_price:.4f} | Alvo (+1% líquido): ${target_price:.4f}\n"
            report += f"- Resultado AGORA (com taxas): ${net_profit_now:+.2f} ({net_profit_pct:+.2f}%)\n"
            report += generate_profit_scenarios(entry_price, qty, total_cost, fee_rate=fee_rate)
            report += "-----------------------------------\n"

        return report
    except Exception as e:
        return f"Erro ao ler posição: {e}"


async def process_ai_response(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """IA com contexto completo + cenários de lucro (educacional) e auditoria."""
    try:
        # Envia "Digitando..."
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        def _infer_symbol_from_text(text: str):
            try:
                t = (text or "").upper()
                m = re.search(r"([A-Z0-9]{2,12}/(?:USDT|BRL))", t)
                if m:
                    return m.group(1)
                # tenta por base (BTC, ETH, etc.)
                bases = []
                try:
                    bases = [s.split('/')[0].upper() for s in (WATCHLIST or [])]
                except Exception:
                    bases = []
                # aliases comuns
                aliases = {
                    'BITCOIN': 'BTC',
                    'ETHEREUM': 'ETH',
                }
                for k, v in aliases.items():
                    if k in t:
                        t += f" {v} "
                for base in bases:
                    if re.search(rf"\b{re.escape(base)}\b", t):
                        return f"{base}/USDT"
            except Exception:
                return None
            return None

        # 1) Snapshot completo
        snap = get_public_snapshot()
        market_overview = snap.get('market_overview', {}) or {}
        last_decisions = snap.get('last_decisions', {}) or {}
        last_block_by_symbol = snap.get('last_trade_block_by_symbol', {}) or {}

        focus_symbol = _infer_symbol_from_text(user_text)

        # 2) Resumo do mercado (WATCHLIST)
        lines = []
        for sym in (WATCHLIST or []):
            data = market_overview.get(sym)
            if not data:
                continue
            p = data.get('price')
            r = data.get('rsi')
            lb = data.get('bb_lower')
            diag = data.get('diagnostic')
            lu = data.get('last_update')
            try:
                p_txt = f"${float(p):.4f}" if p is not None else "N/A"
            except Exception:
                p_txt = "N/A"
            try:
                r_txt = f"{float(r):.1f}" if r is not None else "N/A"
            except Exception:
                r_txt = "N/A"
            try:
                lb_txt = f"${float(lb):.4f}" if lb is not None else "N/A"
            except Exception:
                lb_txt = "N/A"
            lines.append(f"- {sym}: Preço {p_txt}, RSI {r_txt}, BB_inf {lb_txt}, diag={diag or '-'} (upd {lu or '-'})")

        market_context = "\n".join(lines) if lines else "(sem dados de mercado no momento)"

        # 3) Contexto focado (moeda perguntada)
        focus_context = ""
        if focus_symbol:
            md = market_overview.get(focus_symbol)
            if md:
                focus_context += (
                    f"MOEDA PERGUNTADA: {focus_symbol}\n"
                    f"- Preço: {md.get('price')}\n"
                    f"- RSI: {md.get('rsi')}\n"
                    f"- BB Lower: {md.get('bb_lower')}\n"
                    f"- Diagnóstico: {md.get('diagnostic')}\n"
                )
            d = last_decisions.get(focus_symbol)
            if d:
                focus_context += (
                    "\nÚLTIMA DECISÃO DO BOT PARA ESSA MOEDA:\n"
                    f"- Sinal scalper: {d.get('scalper_ok')}\n"
                    f"- Motivo scalper: {d.get('scalper_reason')}\n"
                    f"- Tentou comprar: {d.get('buy_attempted')}\n"
                    f"- Resultado compra: {d.get('buy_result')}\n"
                    f"- Motivo bloqueio: {d.get('block_reason')}\n"
                    f"- Timestamp: {d.get('ts')}\n"
                )
            b = last_block_by_symbol.get(focus_symbol)
            if b:
                focus_context += (
                    "\nÚLTIMO BLOQUEIO REGISTRADO:\n"
                    f"- Ação: {b.get('action')}\n"
                    f"- Motivo: {b.get('reason')}\n"
                    f"- Quando: {b.get('ts')}\n"
                )
        
        # 4) Histórico e posição (inclui cenários)
        db_summary = get_database_summary()
        position_context = get_position_context_string()

        # Prompt Reforçado
        system_prompt = (
            f"{SANDRA_PROMPT}\n\n"
            f"=== REALIDADE DA CONTA (POSIÇÕES + CENÁRIOS) ===\n"
            f"{position_context}\n\n"
            f"=== DADOS DE MERCADO AGORA (USE ESTES NÚMEROS) ===\n"
            f"{market_context}\n\n"
            f"=== CONTEXTO DA MOEDA PERGUNTADA (SE HOUVER) ===\n"
            f"{focus_context or '(usuário não especificou uma moeda)'}\n\n"
            f"=== HISTÓRICO GERAL ===\n"
            f"{db_summary}\n\n"
            f"INSTRUÇÃO DE ENSINO:\n"
            f"- O usuário quer APRENDER risco/retorno.\n"
            f"- Se houver posição aberta, use a seção 'CENÁRIOS' para responder coisas do tipo: 'se vender agora dá X; se subir 0.8% dá Y (líquido)'.\n"
            f"- Explique que taxas reduzem o lucro.\n\n"
            f"DIRETRIZES DE RESPOSTA:\n"
            f"1. Se o usuário perguntar 'quanto estou ganhando?', use o 'Resultado AGORA (com taxas)' do contexto acima.\n"
            f"2. Se perguntar 'por que não comprou?', use 'ÚLTIMA DECISÃO'/'ÚLTIMO BLOQUEIO' acima.\n"
            f"3. NUNCA invente números. Se não houver dados, diga isso.\n"
            f"4. Seja direta e precisa."
        )
        
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Use o modelo mais esperto que tiver
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=300,
            temperature=0 # Temperatura ZERO para máxima precisão matemática
        )
        
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
        
    except Exception as e:
        print(f"Erro na IA: {e}")
        await update.message.reply_text("😵 Tive um erro ao calcular os dados exatos.")


async def telegram_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe áudio, transcreve com Whisper e processa como texto."""
    if not get_openai_client():
        await update.message.reply_text("🧠 IA não configurada para áudio.")
        return

    try:
        await update.message.reply_text("👂 Ouvindo áudio...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

        # Baixa o arquivo
        new_file = await context.bot.get_file(update.message.voice.file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
            await new_file.download_to_drive(custom_path=temp_audio.name)
            temp_path = temp_audio.name
        
        # Transcreve usando Whisper (OpenAI)
        client = get_openai_client()
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        
        text = transcription.text
        os.remove(temp_path) # Limpa arquivo temporário
        
        await update.message.reply_text(f"📝 *Transcrição:* \"{text}\"", parse_mode='Markdown')
        
        # Processa como se fosse texto normal
        await process_ai_response(update, context, user_text=text)

    except Exception as e:
        await update.message.reply_text(f"❌ Erro no áudio: {str(e)}")


async def telegram_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a mensagens de texto usando GPT com contexto do mercado."""
    user_message = update.message.text
    print(f"📩 Mensagem recebida de {update.effective_user.first_name}: {user_message}")

    # Se não tiver OpenAI configurado, responde genérico
    if not get_openai_client():
        await update.message.reply_text("🧠 IA não configurada no servidor. Mas estou ouvindo!")
        return

    await process_ai_response(update, context, user_message)


def run_telegram_bot():
    """Inicia o bot do Telegram em modo de escuta (Polling)."""
    global telegram_app
    
    if not telegram_app:
        print("⚠️ Telegram app não inicializado")
        return
    
    print("Telegram Bot iniciando polling...")
    try:
        # IMPORTANTE: run_polling precisa rodar na thread principal (usa sinais)
        telegram_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Erro fatal no Telegram Bot: {e}")


if __name__ == '__main__':
    try:
        print("="*60)
        print("🏗️  LABORATÓRIO DE TRADING HÍBRIDO")
        print("="*60)
        print(f"API Key: {API_KEY[:8] + '...' if API_KEY else 'NÃO CONFIGURADO'}")
        print(f"Secret: {'✓ Configurado' if SECRET else '✗ Não configurado'}")
        print(f"Símbolo: {SYMBOL}")
        print("="*60)
        
        print("🌐 Iniciando servidor Flask na porta 5000...")
        
        # Flask em thread separada
        def run_flask():
            app.run(host='0.0.0.0', debug=False, port=5000, use_reloader=False, threaded=True)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        print("✅ Servidor Flask iniciado!")

        # Inicia thread de trading
        thread = threading.Thread(target=trading_loop, daemon=True)
        thread.start()

        # --- Scalper Blindado Integrado ao Loop Principal ---
        print("--- 🚀 Scalper Blindado: Módulo Lógico Carregado ---")


        # Se Telegram estiver configurado, roda no MAIN (necessário para polling/sinais)
        if TELEGRAM_TOKEN and TELEGRAM_TOKEN != 'your_telegram_token_here':
            print("Inicializando Telegram Bot...")
            telegram_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

            telegram_app.add_handler(CommandHandler("start", telegram_start))
            telegram_app.add_handler(CommandHandler("ajuda", telegram_help))
            telegram_app.add_handler(CommandHandler("help", telegram_help))
            telegram_app.add_handler(CommandHandler("status", telegram_status))
            telegram_app.add_handler(CommandHandler("saldo", telegram_balance))
            telegram_app.add_handler(CommandHandler("posicao", telegram_position))
            telegram_app.add_handler(CommandHandler("position", telegram_position))
            telegram_app.add_handler(CommandHandler("moedas", telegram_coins))
            telegram_app.add_handler(CommandHandler("coins", telegram_coins))
            telegram_app.add_handler(CommandHandler("relatorio", telegram_report))
            telegram_app.add_handler(CommandHandler("report", telegram_report))
            telegram_app.add_handler(CommandHandler("comprar", telegram_buy))
            telegram_app.add_handler(CommandHandler("buy", telegram_buy))
            telegram_app.add_handler(CommandHandler("converter", telegram_convert))
            telegram_app.add_handler(CommandHandler("convert", telegram_convert))
            telegram_app.add_handler(CommandHandler("grafico", telegram_chart))
            telegram_app.add_handler(CommandHandler("chart", telegram_chart))
            telegram_app.add_handler(CommandHandler("ligar", telegram_start_bot))
            telegram_app.add_handler(CommandHandler("on", telegram_start_bot))
            telegram_app.add_handler(CommandHandler("desligar", telegram_stop_bot))
            telegram_app.add_handler(CommandHandler("off", telegram_stop_bot))
            telegram_app.add_handler(CommandHandler("ia", telegram_ia))
            telegram_app.add_handler(CommandHandler("ai", telegram_ia))
            telegram_app.add_handler(MessageHandler(filters.VOICE, telegram_audio))
            telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_chat))

            print("Telegram pronto. Comandos ativos: /start /ajuda /status /saldo /posicao /moedas /relatorio /comprar /converter /ligar /desligar /ia")

            # Bloqueia aqui (main thread) — Flask + trading seguem em threads
            run_telegram_bot()
        else:
            print("Telegram desabilitado (token inválido)")

            # Mantém o processo principal vivo
            while True:
                time.sleep(60)
            
    except KeyboardInterrupt:
        print("\n⛔ Servidor interrompido pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no main: {e}")
        logging.error(traceback.format_exc())
        print(f"❌ Erro fatal: {e}")
        import traceback as tb
        tb.print_exc()
        input("Pressione ENTER para sair...")
