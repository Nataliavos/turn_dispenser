"""
Prueba de integración insert+select contra Supabase local.

Se omite automáticamente si DATABASE_URL no está definida o Postgres no responde.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from config.settings import clear_settings_cache, get_settings
from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from repositories import ConsultaRepository, get_database, reset_database
from repositories.exceptions import ConexionPersistenciaError, PersistenciaError


def _db_disponible() -> bool:
    clear_settings_cache()
    reset_database()
    settings = get_settings()
    if not settings.database_url:
        return False
    try:
        return get_database(settings).ping()
    except (PersistenciaError, ConexionPersistenciaError):
        return False


pytestmark = pytest.mark.skipif(
    not _db_disponible(),
    reason="Postgres Supabase local no disponible (DATABASE_URL / Docker)",
)


def test_insert_select_consulta_documento() -> None:
    clear_settings_cache()
    reset_database()
    repo = ConsultaRepository(get_database())

    inicio = datetime.now(timezone.utc)
    resultado = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador="9999999999",
        tipo_documento="CC",
        correlation_id="test-d02",
        iniciado_en=inicio,
        resultado_runt=ResultadoRunt(
            nombre="Integracion",
            secciones={"DATOS PERSONALES": {"NOMBRE": "Integracion"}},
            raw_html="<p>runt</p>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="9999999999",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
            raw_html="<p>simit</p>",
        ),
    )
    resultado.finalizar()

    consulta_id = repo.persistir_resultado_consulta(resultado, estacion="pytest")
    repo.agregar_evento(consulta_id, "test d02", fuente="SISTEMA", nivel="info")

    leido = repo.obtener_por_id(consulta_id)
    assert leido is not None
    assert leido.estado == "ok"
    assert leido.resultado_runt is not None
    assert leido.resultado_runt.nombre == "Integracion"
    assert leido.resultado_runt.raw_html == "<p>runt</p>"
    assert leido.resultado_simit is not None
    assert leido.resultado_simit.resumen is not None
    assert leido.resultado_simit.resumen.sin_pendientes is True
    assert len(repo.listar_eventos(consulta_id)) == 1
