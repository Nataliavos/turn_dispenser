#!/usr/bin/env python3
"""
Smoke D-02: insert + select contra Postgres de Supabase local.

Uso (desde la raíz del repo, con .venv activo):
  export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
  # o: cp .env.example .env
  python scripts/smoke_persistencia.py

Requisitos: Docker/Supabase arriba y migraciones aplicadas (docs/supabase-local.md).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import clear_settings_cache, get_settings
from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from repositories import ConsultaRepository, get_database
from repositories.exceptions import PersistenciaError
from utils.logging_setup import setup_logging, get_logger


def main() -> int:
    clear_settings_cache()
    setup_logging(force=True)
    log = get_logger("smoke_persistencia")
    settings = get_settings()

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

    inicio = datetime.now(timezone.utc)
    resultado = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador="0000000000",
        tipo_documento="CC",
        correlation_id="smoke-d02",
        iniciado_en=inicio,
        resultado_runt=ResultadoRunt(
            nombre="Smoke Test",
            estado_licencia="ACTIVO",
            secciones={"DATOS PERSONALES": {"NOMBRE": "Smoke Test"}},
            raw_html="<html><!-- smoke --></html>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="0000000000",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
            raw_html="<html><!-- smoke simit --></html>",
        ),
    )
    resultado.finalizar()

    repo = ConsultaRepository(db)
    consulta_id = repo.persistir_resultado_consulta(
        resultado,
        operador="smoke",
        estacion="local",
        app_version="d02",
    )
    repo.agregar_evento(
        consulta_id,
        "Smoke D-02 OK",
        fuente="SISTEMA",
        nivel="info",
        codigo="SMOKE_D02",
    )

    leido = repo.obtener_por_id(consulta_id)
    eventos = repo.listar_eventos(consulta_id)
    if leido is None:
        log.error("No se recuperó la consulta %s", consulta_id)
        return 1

    log.info(
        "OK id=%s estado=%s runt=%s simit=%s eventos=%s",
        leido.id,
        leido.estado,
        bool(leido.resultado_runt),
        bool(leido.resultado_simit),
        len(eventos),
    )
    print(f"consulta_id={consulta_id}")
    print(f"estado={leido.estado}")
    print(f"runt_nombre={leido.resultado_runt.nombre if leido.resultado_runt else None}")
    print(
        "simit_sin_pendientes="
        f"{leido.resultado_simit.resumen.sin_pendientes if leido.resultado_simit and leido.resultado_simit.resumen else None}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
