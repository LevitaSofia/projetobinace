from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _service_is_active(service: str) -> bool:
    p = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.strip() == "active"


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore seguro do SQLite do projetobinace.")
    ap.add_argument("--db", default="sandra_trading.db", help="Caminho do DB alvo (default: sandra_trading.db)")
    ap.add_argument("--backup", help="Arquivo de backup para restaurar")
    ap.add_argument("--backup-dir", default="backups", help="Pasta onde ficam backups (default: backups)")
    ap.add_argument("--latest", action="store_true", help="Usar o backup mais recente da pasta")
    ap.add_argument("--service", default="projetobinace", help="Nome do serviço systemd (default: projetobinace)")
    ap.add_argument("--stop-service", action="store_true", help="Parar/iniciar o serviço automaticamente")
    args = ap.parse_args()

    db_path = Path(args.db)

    backup_path: Path | None = Path(args.backup) if args.backup else None
    if args.latest:
        bdir = Path(args.backup_dir)
        candidates = sorted((p for p in bdir.glob("backup_*_sandra_trading.db") if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise SystemExit(f"Nenhum backup encontrado em {bdir}")
        backup_path = candidates[0]

    if not backup_path:
        raise SystemExit("Informe --backup /caminho/arquivo.db ou use --latest")

    if not backup_path.exists():
        raise SystemExit(f"Backup não encontrado: {backup_path}")

    service = args.service
    was_active = _service_is_active(service)

    if was_active and not args.stop_service:
        raise SystemExit(
            f"Serviço '{service}' está ativo. Use --stop-service ou pare manualmente: sudo systemctl stop {service}"
        )

    if was_active and args.stop_service:
        _run(["sudo", "systemctl", "stop", service])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if db_path.exists():
        safety = db_path.with_name(f"{db_path.name}.before_restore_{ts}")
        shutil.copy2(db_path, safety)

    shutil.copy2(backup_path, db_path)

    if args.stop_service:
        _run(["sudo", "systemctl", "start", service])

    print(f"OK: restaurado {backup_path} -> {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
