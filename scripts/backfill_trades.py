
import os
import ccxt
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
SECRET = os.getenv('BINANCE_SECRET')
# Ajuste de path para rodar dentro de scripts/
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sandra_trading.db')

def backfill_db():
    if not API_KEY or not SECRET:
        print("❌ Sem credenciais.")
        return

    exchange = ccxt.binance({
        'apiKey': API_KEY,
        'secret': SECRET,
        'enableRateLimit': True
    })

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Pega o timestamp do último trade gravado para saber de onde começar
    cursor.execute("SELECT timestamp FROM trade_history ORDER BY timestamp DESC LIMIT 1")
    last_db_row = cursor.fetchone()
    
    start_ts_ms = 0
    if last_db_row:
        try:
            # Tenta converter ISO para timestamp MS
            last_dt = datetime.fromisoformat(last_db_row[0])
            start_ts_ms = int(last_dt.timestamp() * 1000)
            print(f"📅 Último registro no DB: {last_db_row[0]}")
        except:
            pass
    
    # Se não tiver nada ou for muito antigo, pega dos últimos 15 dias
    if start_ts_ms == 0:
        start_ts_ms = int(datetime.now().timestamp() * 1000) - (15 * 24 * 60 * 60 * 1000)

    # Adiciona 1 segundo para não duplicar o último exato
    start_ts_ms += 1000

    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 'LTC/USDT', 'ICP/USDT', 'XRP/USDT', 'USDC/USDT']
    count_added = 0

    print(f"📥 Baixando trades da Binance a partir de {datetime.fromtimestamp(start_ts_ms/1000)}...")

    for symbol in symbols:
        try:
            trades = exchange.fetch_my_trades(symbol, since=start_ts_ms)
            for t in trades:
                # Evita duplicação por ID do trade (Order ID)
                order_id = str(t['order'])
                cursor.execute("SELECT id FROM trade_history WHERE json_extract(json_data, '$.order_id') = ?", (order_id,))
                if cursor.fetchone():
                    continue

                # Monta o JSON formatado igual ao do server.py
                # NOTA: O server.py salva BUY e SELL. 
                # Precisamos inferir dados de lucro para SELL.
                # Como é backfill, não temos o "qty" da compra original fácil aqui para calcular lucro exato.
                # Vamos simplificar: salvar o evento bruto.
                # CORREÇÃO: Para o relatório funcionar, o SELL precisa ter 'net_profit_usdt'.
                # Vamos tentar estimar o lucro pegando a última compra desse symbol?
                # É complexo. Vamos salvar o dado básico e o relatório vai mostrar o que der.
                
                # Melhor: Se for SELL, tentar achar uma compra aberta? 
                # O script do relatório pega entry_price do JSON. Se não tiver, vai dar erro ou zero.
                # Vamos tentar preencher com dados da Binance se disponíveis.
                
                side = t['side']
                price = t['price']
                qty = t['amount']
                cost = t['cost']
                fee_cost = t['fee']['cost'] if t.get('fee') else 0.0
                ts_iso = t['datetime']
                
                trade_data = {
                    'timestamp': ts_iso,
                    'side': side,
                    'symbol': symbol,
                    'price': price,
                    'qty': qty,
                    'fees': fee_cost,
                    'order_id': order_id,
                    'mode': 'REAL (Backfill)',
                    'time': ts_iso.split('T')[1].split('.')[0]
                }

                # Se for SELL, precisamos de entry_price e net_profit para o Excel ficar bonito.
                if side == 'sell':
                    # Tenta achar a última compra desse par no DB para pegar o preço de entrada
                    # Isso é uma estimativa "fifo" simplificada
                    cursor.execute(
                        "SELECT json_data FROM trade_history WHERE symbol=? AND side='buy' AND timestamp < ? ORDER BY timestamp DESC LIMIT 1", 
                        (symbol, ts_iso)
                    )
                    buy_row = cursor.fetchone()
                    entry_price = price # fallback
                    if buy_row:
                        buy_data = json.loads(buy_row[0])
                        entry_price = float(buy_data.get('price', price))
                    
                    trade_data['entry_price'] = entry_price
                    trade_data['exit_price'] = price
                    
                    # Lucro aproximado
                    gross_profit = (price - entry_price) * qty
                    net_profit = gross_profit - (fee_cost * 2) # Estima taxa de entrada + saída
                    trade_data['net_profit_usdt'] = net_profit
                    trade_data['net_profit_pct'] = (net_profit / (entry_price * qty)) * 100 if entry_price else 0

                # Insere no SQLite
                # Schema: strategy, symbol, side, price, qty, profit_usdt, profit_pct, timestamp, json_data
                try:
                    cursor.execute(
                        """
                        INSERT INTO trade_history (strategy, symbol, side, price, qty, profit_usdt, profit_pct, timestamp, json_data) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            'Backfill',
                            symbol,
                            side,
                            price,
                            qty,
                            trade_data.get('net_profit_usdt', 0),
                            trade_data.get('net_profit_pct', 0),
                            ts_iso,
                            json.dumps(trade_data)
                        )
                    )
                    count_added += 1
                    print(f"✅ Recuperado: {ts_iso} {side} {symbol}")
                except Exception as db_err:
                    print(f"⚠️ Erro ao inserir no DB: {db_err}")

        except Exception as e:
            print(f"⚠️ Erro ao processar {symbol}: {e}")

    conn.commit()
    conn.close()
    print(f"\n✨ Processo finalizado. {count_added} trades recuperados.")

if __name__ == "__main__":
    backfill_db()
