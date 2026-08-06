#!/usr/bin/env python3
"""
Retención F-07: nullificar ``raw_html`` antiguo en resultados_runt / resultados_simit.

Política piloto: ≤ 30 días (configurable). No borra maestros ni hechos tipados.
No re-consulta portales.

Uso (raíz del repo, .venv, DATABASE_URL):

  # Contar candidatas sin modificar
  python scripts/purge_raw_html.py --dry-run

  # Nullificar HTML con más de 30 días
  python scripts/purge_raw_html.py

  # Ventana personalizada
  python scripts/purge_raw_html.py --days 14 --dry-run

Cron semanal (ejemplo, documentado en runbook):

  0 3 * * 0 cd /ruta/turn_dispenser && .venv/bin/python scripts/purge_raw_html.py --days 30
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import clear_settings_cache, get_settings
from repositories import ConsultaRepository, get_database, reset_database
from repositories.exceptions import PersistenciaError
from repositories.purge_raw_html import DEFAULT_RETENTION_DAYS, ejecutar_purge_raw_html
from utils.logging_setup import get_logger, setup_logging


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Nullifica raw_html en snapshots fuera de la ventana de retención "
            "(F-07). Preferido frente a borrar filas."
        )
    )
    p.add_argument(
        "--days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Edad mínima en días para nullificar (default {DEFAULT_RETENTION_DAYS})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo cuenta candidatas; no escribe en BD",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    clear_settings_cache()
    reset_database()
    setup_logging(force=True)
    log = get_logger("purge_raw_html")
    settings = get_settings()

    if args.days < 1:
        log.error("--days debe ser >= 1")
        return 2

    if not settings.database_url:
        log.error("DATABASE_URL no configurada (.env / entorno).")
        return 2

    db = get_database(settings)
    try:
        if not db.ping():
            log.error("Ping a Postgres falló.")
            return 1
    except PersistenciaError as exc:
        log.error("Conexión fallida: %s", exc.mensaje)
        return 1

    repo = ConsultaRepository(db)
    resumen = ejecutar_purge_raw_html(
        repo,
        days=args.days,
        dry_run=args.dry_run,
        log=log,
    )

    print(
        f"RESULTADO: days={resumen.days} cutoff={resumen.cutoff.isoformat()} "
        f"candidatas_runt={resumen.candidatas_runt} "
        f"candidatas_simit={resumen.candidatas_simit} "
        f"actualizadas_runt={resumen.actualizadas_runt} "
        f"actualizadas_simit={resumen.actualizadas_simit} "
        f"dry_run={resumen.dry_run}",
        flush=True,
    )
    if resumen.errores:
        print("RESULTADO GLOBAL: FAIL", flush=True)
        return 1
    print("RESULTADO GLOBAL: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
