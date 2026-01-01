from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path


def backup_sqlite_db(
    src_db_path: str,
    backup_dir: str = "backups",
    keep_last: int = 50,
) -> str:
    """Cria um backup consistente do SQLite (snapshot) e faz rotação.

    - Usa a API sqlite3.Connection.backup (mais seguro que copiar o arquivo "no seco").
    - Retém apenas os N backups mais recentes.

    Retorna o caminho do backup criado.
    """
    src = Path(src_db_path)
    if not src.exists():
        raise FileNotFoundError(f"DB não encontrado: {src_db_path}")

    dst_dir = Path(backup_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = dst_dir / f"backup_{ts}_{src.name}"

    src_conn = sqlite3.connect(str(src), timeout=30)
    try:
        dst_conn = sqlite3.connect(str(dst), timeout=30)
        try:
            src_conn.backup(dst_conn)
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    _prune_old_backups(dst_dir=dst_dir, db_name=src.name, keep_last=keep_last)
    return str(dst)


def _prune_old_backups(dst_dir: Path, db_name: str, keep_last: int) -> None:
    if keep_last <= 0:
        return

    candidates = sorted(
        (p for p in dst_dir.glob(f"backup_*_{db_name}") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for p in candidates[keep_last:]:
        try:
            p.unlink()
        except Exception:
            pass


def env_truthy(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")
