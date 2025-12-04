import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

# 1. Instalação automática do ccxt se não existir
try:
    import ccxt
except ImportError:
    print("📦 Instalando biblioteca 'ccxt' necessária...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt"])
    import ccxt

# --- SUAS CHAVES (Preenchidas automaticamente com base no que você me passou) ---
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET  = os.getenv('BINANCE_SECRET')

def testar_conexao():
    print("\n" + "="*50)
    print("🚀 INICIANDO TESTE DE CONEXÃO BINANCE (LOCAL)")
    print("="*50)
    
    try:
        # Configura a conexão
        exchange = ccxt.binance({
            'apiKey': API_KEY,
            'secret': SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        
        print("📡 Conectando aos servidores da Binance...")
        
        # 1. Teste de Leitura de Saldo
        balance = exchange.fetch_balance()
        usdt_total = balance['total'].get('USDT', 0.0)
        usdt_free = balance['free'].get('USDT', 0.0)
        
        # 2. Teste de Detalhes da Conta (VIP, Taxas)
        info = exchange.private_get_account()
        maker_fee = float(info.get('makerCommission', 0)) / 100
        taker_fee = float(info.get('takerCommission', 0)) / 100
        can_trade = info.get('canTrade')
        
        print("\n✅ SUCESSO! CONEXÃO ESTABELECIDA COM ÊXITO!")
        print("-" * 50)
        print(f"💰 SALDO TOTAL USDT:   ${usdt_total:.2f}")
        print(f"🔓 SALDO LIVRE USDT:   ${usdt_free:.2f}")
        print("-" * 50)
        print(f"👤 TIPO DE CONTA:      {info.get('accountType')}")
        print(f"🚦 PERMISSÃO DE TRADE: {'✅ SIM' if can_trade else '❌ NÃO'}")
        print(f"💸 TAXAS (Maker/Taker): {maker_fee}% / {taker_fee}%")
        print(f"🔑 PERMISSÕES DA CHAVE: {', '.join(info.get('permissions', []))}")
        print("=" * 50)
        print("\nCONCLUSÃO:")
        print("Se você está vendo os dados acima, suas chaves estão 100% funcionais.")
        print("O problema no VPS é EXCLUSIVAMENTE o bloqueio de região (IP dos EUA).")
        
    except Exception as e:
        print("\n❌ FALHA NA CONEXÃO:")
        print(f"Erro: {e}")
        print("\nPossíveis causas:")
        print("1. Chaves API incorretas.")
        print("2. Sem internet.")
        print("3. Relógio do computador dessincronizado.")

if __name__ == "__main__":
    testar_conexao()
