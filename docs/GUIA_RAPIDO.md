# ⚡ Guia Rápido (Operação)

Este guia é para **rodar / parar / verificar** o sistema rapidamente.

---

## ✅ Pré-requisitos

- Python 3
- Dependências instaladas no ambiente virtual:

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

- Arquivo `.env` configurado (chaves Binance/Telegram etc.).

---

## ▶️ Iniciar

### Foreground (debug)

```bash
./venv/bin/python3 server.py
```

### Background (recomendado em servidor)

```bash
nohup ./venv/bin/python3 server.py > server.log 2>&1 & echo $! > server.pid
```

Acompanhar logs:

```bash
tail -f server.log
```

---

## ⏹️ Parar

Se você salvou o PID:

```bash
kill $(cat server.pid)
```

Se precisar achar o processo manualmente:

```bash
ps aux | grep -E "python.*server\.py" | grep -v grep
```

---

## 🌐 URLs (Web)

- Dashboard: `http://SEU_IP:5000/`
- Charts: `http://SEU_IP:5000/charts`
- Performance: `http://SEU_IP:5000/performance`

---

## 🔌 Endpoints (API)

- `GET /api/status`
- `GET /api/positions`
- `GET /api/watchlist`
- `GET /api/logs`
- `GET /api/chart/<symbol_safe>`
- `POST /api/command/<cmd>`

Teste rápido:

```bash
curl -s http://127.0.0.1:5000/api/status
curl -s http://127.0.0.1:5000/api/watchlist | head
curl -s http://127.0.0.1:5000/api/positions
```

---

## 🧯 Checklist: “Web não conecta / não mostra dados”

1) **Acesse pela URL certa**
- Correto: `http://SEU_IP:5000/`
- Errado: abrir o HTML via `file://...`

2) **Veja a linha de diagnóstico no painel SYSTEM LOGS**
- `API: OK (...)` → backend acessível
- `API: falha (...)` + linhas `UI/ERROR` → erro de rede/HTTP

3) **Causas comuns**
- Porta `5000` bloqueada no firewall/security group
- Mixed content (abrir a UI em `https://...` e o backend em `http://...`)
- Cliente sem acesso à CDN do gráfico (o painel continua funcionando; apenas o gráfico pode ficar vazio)

---

## 🤖 Telegram (atalho)

- `/ajuda` ou `/help` — lista de comandos
- `/moedas` — **Relatório Profissional (Carteira + Radar)**

---

## 🧩 Rodar como serviço (systemd)

Isso mantém o sistema rodando mesmo após fechar o terminal e pode iniciar automaticamente no boot.

### 1) Instalar o serviço

O unit file está em:

- `scripts/systemd/projetobinace.service`

Copie para o systemd (precisa sudo):

```bash
sudo cp /home/ubuntu/projetobinace/scripts/systemd/projetobinace.service /etc/systemd/system/projetobinace.service
sudo systemctl daemon-reload
```

### 2) Iniciar e habilitar no boot

```bash
sudo systemctl enable --now projetobinace
```

### 3) Ver status e logs

```bash
sudo systemctl status projetobinace --no-pager
journalctl -u projetobinace -f
```

### 4) Parar / reiniciar

```bash
sudo systemctl stop projetobinace
sudo systemctl restart projetobinace
```

### Observações

- O serviço lê variáveis do `.env` via `EnvironmentFile`.
- Se o projeto não estiver em `/home/ubuntu/projetobinace`, edite os caminhos dentro do unit file.

---

## 📧 Relatório diário (Gmail)

O sistema pode enviar um fechamento diário por e-mail (e também replica no Telegram).

### 1) Configurar no `.env`

```env
EMAIL_ENABLED=true
EMAIL_TO=seuemail@gmail.com

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seuemail@gmail.com
SMTP_PASS=SUA_SENHA_DE_APP_DO_GOOGLE

DAILY_EMAIL_REPORT_HOUR=23
DAILY_EMAIL_REPORT_MINUTE=59
```

### 2) Requisitos do Gmail

- Ativar 2FA na conta Google
- Criar uma "Senha de app" (App Password) para Mail

### 3) Ver logs

```bash
journalctl -u projetobinace -f
```

---

## 🗄️ Banco de dados (SQLite) + Backup/Restore

O sistema persiste as execuções importantes no SQLite:

- Arquivo: `sandra_trading.db`
- Tabelas principais:
	- `trade_history` (BUY/SELL e PnL)
	- `system_state` (snapshot do estado do painel)
	- `system_events` (eventos importantes: comandos manuais, backups, etc.)

### ✅ Backup automático

Por padrão, o bot cria **backup automático** do SQLite após cada *SELL real* (snapshot consistente), com rotação.

Configuração opcional no `.env`:

```env
DB_BACKUP_ENABLED=true
DB_BACKUP_DIR=backups
DB_BACKUP_KEEP_LAST=50
```

Os backups ficam em:

- `./backups/backup_YYYYMMDD_HHMMSS_sandra_trading.db`

### ♻️ Restore (recuperar o sistema)

Passo a passo (recomendado):

1) Pare o serviço:

```bash
sudo systemctl stop projetobinace
```

2) Faça uma cópia de segurança do DB atual (por precaução):

```bash
cp -a sandra_trading.db sandra_trading.db.before_restore
```

3) Restaure um backup (substitui o banco atual):

```bash
cp -a backups/backup_YYYYMMDD_HHMMSS_sandra_trading.db sandra_trading.db
```

4) Suba de novo:

```bash
sudo systemctl start projetobinace
```

5) Verifique:

```bash
curl -s http://127.0.0.1:5000/api/status
journalctl -u projetobinace -n 50 --no-pager
```
