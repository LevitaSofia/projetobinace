import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import sys

# Define scope
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Creds location (relative to project root)
creds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')

SHEET_ID = "19wkbjAT4L6KPXXSRexEEbMs95nsAjNwglDZx81bllnw"

def test_connection():
    try:
        if not os.path.exists(creds_path):
            print(f"❌ Credentials not found at: {creds_path}")
            return

        creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        client = gspread.authorize(creds)
        
        print(f"🔌 Tentando abrir planilha: {SHEET_ID}...")
        sheet = client.open_by_key(SHEET_ID)
        
        print(f"✅ SUCESSO! Conectado a: {sheet.title}")
        print("Abas disponíveis:")
        for ws in sheet.worksheets():
            print(f" - {ws.title}")
            
    except Exception as e:
        print(f"❌ FALHA: {e}")
        # Check for 403
        if "403" in str(e):
             print("\n⚠️  ERRO DE PERMISSÃO: Você precisa compartilhar a planilha com o email do bot:")
             # Try to parse client_email from json without importing json just for this msg
             print("   sandra-bot@gen-lang-client-0424902422.iam.gserviceaccount.com")

if __name__ == "__main__":
    test_connection()
