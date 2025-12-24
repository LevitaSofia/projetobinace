import os
import sqlite3
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage


def _iso_date(d: datetime) -> str:
    return d.strftime('%Y-%m-%d')


def build_daily_summary(db_path: str, date_str: str | None = None, days_rolling: int = 7) -> dict:
    """Gera resumo do dia a partir do SQLite (trade_history).

    Espera timestamps ISO (YYYY-MM-DD...).
    Considera apenas trades de venda (side='sell') para PnL realizado.
    """
    if not date_str:
        date_str = _iso_date(datetime.utcnow())

    result = {
        'date': date_str,
        'total_trades': 0,
        'wins': 0,
        'losses': 0,
        'net_profit_usdt': 0.0,
        'best_trade_usdt': 0.0,
        'worst_trade_usdt': 0.0,
        'symbols': [],
        'rolling_days': days_rolling,
        'rolling_net_profit_usdt': 0.0,
    }

    if not os.path.exists(db_path):
        return result

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        # Trades do dia (apenas vendas)
        cur.execute(
            """
            SELECT symbol, profit_usdt
            FROM trade_history
            WHERE side = 'sell'
              AND substr(timestamp, 1, 10) = ?
            """,
            (date_str,),
        )
        rows = cur.fetchall() or []

        profits = []
        symbols = set()
        for symbol, profit_usdt in rows:
            try:
                p = float(profit_usdt or 0.0)
            except Exception:
                p = 0.0
            profits.append(p)
            if symbol:
                symbols.add(symbol)

        result['total_trades'] = len(profits)
        result['wins'] = sum(1 for p in profits if p > 0)
        result['losses'] = sum(1 for p in profits if p < 0)
        result['net_profit_usdt'] = float(sum(profits))
        result['best_trade_usdt'] = float(max(profits)) if profits else 0.0
        result['worst_trade_usdt'] = float(min(profits)) if profits else 0.0
        result['symbols'] = sorted(symbols)

        # Rolling window (últimos N dias incluindo hoje)
        try:
            day = datetime.strptime(date_str, '%Y-%m-%d')
        except Exception:
            day = datetime.utcnow()
        start = day - timedelta(days=max(0, days_rolling - 1))
        start_str = _iso_date(start)

        cur.execute(
            """
            SELECT COALESCE(SUM(profit_usdt), 0)
            FROM trade_history
            WHERE side = 'sell'
              AND substr(timestamp, 1, 10) >= ?
              AND substr(timestamp, 1, 10) <= ?
            """,
            (start_str, date_str),
        )
        rolling = cur.fetchone()
        try:
            result['rolling_net_profit_usdt'] = float((rolling[0] if rolling else 0.0) or 0.0)
        except Exception:
            result['rolling_net_profit_usdt'] = 0.0

        return result
    finally:
        conn.close()


def format_daily_summary_text(summary: dict) -> str:
    date_str = summary.get('date', '')
    total = summary.get('total_trades', 0)
    wins = summary.get('wins', 0)
    losses = summary.get('losses', 0)
    net = float(summary.get('net_profit_usdt', 0.0) or 0.0)
    best = float(summary.get('best_trade_usdt', 0.0) or 0.0)
    worst = float(summary.get('worst_trade_usdt', 0.0) or 0.0)
    rolling_days = summary.get('rolling_days', 7)
    rolling_net = float(summary.get('rolling_net_profit_usdt', 0.0) or 0.0)
    symbols = summary.get('symbols', []) or []

    sym_txt = ', '.join(symbols) if symbols else '(nenhuma)'

    return (
        f"📩 FECHAMENTO DO DIA ({date_str})\n\n"
        f"Trades (vendas): {total} | ✅ {wins} | 🔻 {losses}\n"
        f"💰 PnL líquido (USDT): {net:+.2f}\n"
        f"🏆 Melhor trade: {best:+.2f} USDT\n"
        f"🧨 Pior trade: {worst:+.2f} USDT\n\n"
        f"📌 Moedas: {sym_txt}\n\n"
        f"📈 Acumulado {rolling_days}d (USDT): {rolling_net:+.2f}\n"
    )


def send_email_smtp(subject: str, body: str) -> bool:
    """Envia e-mail via SMTP usando variáveis de ambiente.

    Variáveis:
      EMAIL_ENABLED=true/false
      EMAIL_TO
      SMTP_HOST
      SMTP_PORT
      SMTP_USER
      SMTP_PASS
    """
    enabled = str(os.getenv('EMAIL_ENABLED', 'false')).strip().lower() in ('1', 'true', 'yes', 'on')
    if not enabled:
        return False

    email_to = (os.getenv('EMAIL_TO') or '').strip()
    host = (os.getenv('SMTP_HOST') or '').strip()
    port = int(os.getenv('SMTP_PORT', '587') or 587)
    user = (os.getenv('SMTP_USER') or '').strip()
    password = (os.getenv('SMTP_PASS') or '')

    # Normaliza senha de app (às vezes vem com espaços ao copiar/colar)
    password = ''.join(password.split())

    if not (email_to and host and user and password):
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = email_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception:
        return False
