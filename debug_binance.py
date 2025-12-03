import os
import ccxt
from dotenv import load_dotenv

# Carrega variáveis
load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
secret = os.getenv('BINANCE_SECRET')

print(
    f"API Key carregada: {api_key[:4]}...{api_key[-4:] if api_key else 'None'}")
print(f"Secret carregada: {'Sim' if secret else 'Não'}")

if not api_key or not secret:
    print("ERRO: Chaves não encontradas no arquivo .env")
    exit()

print("\nTentando conectar na Binance...")
exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True
})

try:
    # Teste 1: Hora do Servidor (Não precisa de chave)
    print("1. Testando conexão pública (Time)...")
    time = exchange.fetch_time()
    print(f"   Sucesso! Timestamp: {time}")

    # Teste 2: Saldo (Precisa de chave)
    print("\n2. Testando autenticação (Saldo)...")
    balance = exchange.fetch_balance()
    print("   Sucesso! Autenticação funcionou.")

    total_usdt = balance['total'].get('USDT', 0)
    print(f"   Saldo USDT: {total_usdt}")

    # Teste 3: Permissões
    print("\n3. Verificando permissões...")
    info = exchange.private_get_account()
    print(f"   Permissões: {info.get('permissions')}")
    print(f"   Can Trade: {info.get('canTrade')}")
    print(f"   Can Withdraw: {info.get('canWithdraw')}")

except ccxt.AuthenticationError as e:
    print(f"\n❌ ERRO DE AUTENTICAÇÃO: {e}")
    print("Verifique se suas API Keys estão corretas e se o IP está liberado na Binance.")
except ccxt.NetworkError as e:
    print(f"\n❌ ERRO DE REDE: {e}")
    print("Verifique sua conexão com a internet.")
except Exception as e:
    print(f"\n❌ ERRO DESCONHECIDO: {e}")
