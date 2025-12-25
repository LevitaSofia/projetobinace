import sqlite3
import pandas as pd
import json
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandra_trading.db")

def conectar_db():
    if not os.path.exists(DB_NAME):
        print(f"❌ Erro: O banco de dados '{DB_NAME}' não foi encontrado.")
        return None
    return sqlite3.connect(DB_NAME)

def gerar_relatorio():
    conn = conectar_db()
    if not conn:
        return

    print("\n" + "="*60)
    print(f"📊 EXTRATO FINANCEIRO DO ROBÔ (Lendo {DB_NAME})")
    print("="*60)

    # --- 1. HISTÓRICO DE VENDAS (REALIZADO) ---
    query_vendas = """
    SELECT 
        timestamp,
        symbol,
        price as sell_price,
        qty,
        profit_usdt,
        profit_pct,
        json_data
    FROM trade_history 
    WHERE side = 'sell'
    ORDER BY timestamp DESC
    """
    
    try:
        df = pd.read_sql_query(query_vendas, conn)
        
        if not df.empty:
            # Processamento de dados
            # Converte timestamp ISO para datetime e formata
            df['Data_Venda'] = pd.to_datetime(df['timestamp'], errors='coerce').dt.strftime('%d/%m %H:%M')
            
            # Tentar extrair preço de compra do JSON
            def get_entry_price(row):
                try:
                    data = json.loads(row['json_data'])
                    return float(data.get('entry_price', 0))
                except:
                    return 0.0

            df['Compra_$'] = df.apply(get_entry_price, axis=1)
            
            # Formatação para exibição
            display_df = df.copy()
            display_df['Lucro_USDT'] = display_df['profit_usdt'].map('${:,.2f}'.format)
            display_df['Lucro_Perc'] = (display_df['profit_pct'] * 100).map('{:,.2f}%'.format)
            display_df['Compra_$'] = display_df['Compra_$'].map('${:,.4f}'.format)
            display_df['Venda_$'] = display_df['sell_price'].map('${:,.4f}'.format)
            
            print(f"\n✅ HISTÓRICO DE VENDAS (LUCRO REALIZADO):")
            # Renomear colunas para exibição
            cols_map = {
                'symbol': 'Par',
                'Compra_$': 'Compra ($)',
                'Venda_$': 'Venda ($)',
                'Lucro_Perc': 'Lucro %',
                'Lucro_USDT': 'Lucro USDT'
            }
            display_df = display_df.rename(columns=cols_map)
            print(display_df[['Data_Venda', 'Par', 'Compra ($)', 'Venda ($)', 'Lucro %', 'Lucro USDT']].to_string(index=False))
            
            # Totais
            total_lucro = df['profit_usdt'].sum()
            total_volume = (df['sell_price'] * df['qty']).sum()
            
            print("-" * 60)
            print(f"💰 RESUMO GERAL:")
            print(f"   Volume de Vendas:     ${total_volume:.2f}")
            print(f"   LUCRO LÍQUIDO TOTAL:  ${total_lucro:.2f} " + ("🟢" if total_lucro > 0 else "🔴"))
            
        else:
            print("\nℹ️ Nenhuma venda registrada ainda.")

    except Exception as e:
        print(f"⚠️ Erro ao ler histórico: {e}")
        import traceback
        traceback.print_exc()

    # --- 2. POSIÇÕES ABERTAS (DO SYSTEM_STATE) ---
    print("\n" + "="*60)
    print("🔓 POSIÇÕES ABERTAS (EM ANDAMENTO)")
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key = 'lab_state'")
        row = cursor.fetchone()
        
        if row:
            state = json.loads(row[0])
            # Navegar até as posições: strategies -> aggressive -> positions
            positions = state.get('strategies', {}).get('aggressive', {}).get('positions', {})
            
            if positions:
                lista_pos = []
                for symbol, data in positions.items():
                    lista_pos.append({
                        'Par': symbol,
                        'Data_Compra': pd.to_datetime(data.get('entry_time')).strftime('%d/%m %H:%M'),
                        'Qtd': data.get('qty'),
                        'Preco_Entrada': data.get('entry_price'),
                        'Investido': data.get('entry_cost_usdt', 0)
                    })
                
                df_pos = pd.DataFrame(lista_pos)
                # Formatação
                df_pos['Preco_Entrada'] = df_pos['Preco_Entrada'].map('${:,.4f}'.format)
                df_pos['Investido_Fmt'] = df_pos['Investido'].map('${:,.2f}'.format)
                
                print(df_pos[['Data_Compra', 'Par', 'Qtd', 'Preco_Entrada', 'Investido_Fmt']].to_string(index=False))
                print(f"\n🎲 Total Investido Agora: ${df_pos['Investido'].sum():.2f}")
            else:
                print("ℹ️ Nenhuma posição aberta no momento.")
        else:
            print("⚠️ Estado do sistema não encontrado.")

    except Exception as e:
        print(f"⚠️ Erro ao ler posições abertas: {e}")

    conn.close()
    print("="*60 + "\n")

if __name__ == "__main__":
    gerar_relatorio()
