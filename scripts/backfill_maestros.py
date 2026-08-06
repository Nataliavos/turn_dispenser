#!/usr/bin/env python3
"""
Backfill F-06: poblar maestros/hechos tipados desde snapshots capa A.

Idempotente (upsert F-02). No re-consulta RUNT/SIMIT.

Uso (raíz del repo, .venv, DATABASE_URL):

  # Solo reporte — no escribe
  python scripts/backfill_maestros.py --dry-run

  # Ejecutar (todas las consultas con resultados)
  python scripts/backfill_maestros.py

  # Solo sin FK resuelta + tope
  python scripts/backfill_maestros.py --solo-sin-fk --limit 100

  # Ventana de fechas (ISO UTC)
  python scripts/backfill_maestros.py --desde 2026-07-01 --hasta 2026-08-01T00:00:00Z
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import clear_settings_cache, get_settings
from repositories import ConsultaRepository, get_database, reset_database
from repositories.backfill import ejecutar_backfill
from repositories.exceptions import PersistenciaError
from utils.logging_setup import get_logger, setup_logging


def _parse_fecha(texto: Optional[str]) -> Optional[datetime]:
    if not texto:
        return None
    raw = texto.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Backfill de personas/vehículos/hechos tipados desde resultados_* "
            "(F-06). Idempotente."
        )
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Describe el plan de normalización sin escribir en BD",
    )
    p.add_argument(
        "--desde",
        metavar="ISO",
        help="Incluir consultas con iniciado_en/created_at >= fecha (UTC)",
    )
    p.add_argument(
        "--hasta",
        metavar="ISO",
        help="Incluir consultas con iniciado_en/created_at <= fecha (UTC)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo de consultas a procesar (más antiguas primero)",
    )
    p.add_argument(
        "--solo-sin-fk",
        action="store_true",
        help=(
            "Solo DOCUMENTO sin persona_id o PLACA sin vehiculo_id "
            "(omitir ya normalizadas)"
        ),
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    clear_settings_cache()
    reset_database()
    setup_logging(force=True)
    log = get_logger("backfill_maestros")
    settings = get_settings()

    if not settings.database_url:
        log.error("DATABASE_URL no configurada (.env / entorno).")
        return 2

    try:
        desde = _parse_fecha(args.desde)
        hasta = _parse_fecha(args.hasta)
    except ValueError as exc:
        log.error("Fecha inválida: %s", exc)
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
    resumen = ejecutar_backfill(
        repo,
        dry_run=args.dry_run,
        desde=desde,
        hasta=hasta,
        limit=args.limit,
        solo_sin_fk=args.solo_sin_fk,
        log=log,
    )

    print(
        f"RESULTADO: candidatas={resumen.candidatas} "
        f"procesadas={resumen.procesadas} omitidas={resumen.omitidas} "
        f"errores={resumen.errores} dry_run={resumen.dry_run}",
        flush=True,
    )
    if resumen.errores:
        print("RESULTADO GLOBAL: FAIL (hubo errores por fila; ver log)", flush=True)
        return 1
    print("RESULTADO GLOBAL: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
