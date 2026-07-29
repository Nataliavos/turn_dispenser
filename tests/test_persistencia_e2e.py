"""
Verificación E2E de persistencia (D-04).

Escenarios contra Postgres de Supabase local con hechos mockeados
(sin abrir Chromium ni portales). Omite la suite si no hay DATABASE_URL/Docker.

Correspondencia con docs/VALIDACION_PERSISTENCIA.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator, List
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from config.settings import Settings, clear_settings_cache, get_settings
from controllers.consulta_controller import ConsultaController
from controllers.persistencia_post_consulta import intentar_persistir_resultado
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from repositories import ConsultaRepository, get_database, reset_database
from repositories.exceptions import ConexionPersistenciaError, PersistenciaError

_COLUMNAS_ELEGIBILIDAD_PROHIBIDAS = (
    "apto",
    "puede_tramitar",
    "elegible",
    "elegibilidad",
    "dictamen",
)


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


@pytest.fixture
def repo() -> Iterator[ConsultaRepository]:
    clear_settings_cache()
    reset_database()
    yield ConsultaRepository(get_database())


def _settings_ok(**overrides: Any) -> Settings:
    base = get_settings()
    # Settings is frozen; rebuild with same fields.
    data = {
        "app_env": base.app_env,
        "debug": base.debug,
        "log_level": base.log_level,
        "log_file": base.log_file,
        "runt_url": base.runt_url,
        "simit_url": base.simit_url,
        "browser_headless": base.browser_headless,
        "runt_slow_mo_ms": base.runt_slow_mo_ms,
        "simit_slow_mo_ms": base.simit_slow_mo_ms,
        "navigation_timeout_ms": base.navigation_timeout_ms,
        "runt_network_idle_timeout_ms": base.runt_network_idle_timeout_ms,
        "simit_network_idle_timeout_ms": base.simit_network_idle_timeout_ms,
        "simit_results_timeout_ms": base.simit_results_timeout_ms,
        "runt_captcha_timeout_ms": base.runt_captcha_timeout_ms,
        "database_url": base.database_url,
        "db_connect_timeout_s": base.db_connect_timeout_s,
        "persistencia_enabled": True,
        "operador": "d04",
        "estacion": "pytest-e2e",
        "app_version": "d04",
        "supabase_url": base.supabase_url,
        "supabase_anon_key": base.supabase_anon_key,
        "supabase_service_role_key": base.supabase_service_role_key,
    }
    data.update(overrides)
    return Settings(**data)


def _assert_sin_elegibilidad_en_esquema(repo: ConsultaRepository) -> None:
    with repo._db.connection() as conn:
        rows = conn.execute(
            """
            select table_name, column_name
              from information_schema.columns
             where table_schema = 'public'
               and table_name in (
                    'consultas', 'resultados_runt',
                    'resultados_simit', 'eventos_consulta'
               )
            """
        ).fetchall()
    nombres = {str(r["column_name"]).lower() for r in rows}
    prohibidas = [c for c in _COLUMNAS_ELEGIBILIDAD_PROHIBIDAS if c in nombres]
    assert not prohibidas, f"Columnas de elegibilidad encontradas: {prohibidas}"


def test_e2e_01_documento_ok_runt_y_simit(repo: ConsultaRepository) -> None:
    """Escenario 1: DOCUMENTO ok → cabecera + ambas fuentes + raw_html."""
    _assert_sin_elegibilidad_en_esquema(repo)

    controller = ConsultaController()
    controller._runt.consultar_ciudadano = MagicMock(  # type: ignore[method-assign]
        return_value=ResultadoRunt(
            nombre="E2E Documento",
            estado_licencia="ACTIVO",
            secciones={"DATOS PERSONALES": {"NOMBRE": "E2E Documento"}},
            raw_html="<html id='runt-e2e'>ok</html>",
            tiene_multas_inferidas=False,
        )
    )
    controller._simit.consultar = MagicMock(  # type: ignore[method-assign]
        return_value=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="1111111111",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
            raw_html="<html id='simit-e2e'>ok</html>",
        )
    )

    resultado = controller.consultar(
        ConsultaParams(
            modo="DOCUMENTO",
            identificador="1111111111",
            tipo_documento="CC",
        ),
        resolver_captcha=lambda _b: "x",
        debug=False,
    )

    assert resultado.estado_global == "ok"
    assert resultado.persistido is True
    assert isinstance(resultado.consulta_db_id, UUID)

    leido = repo.obtener_por_id(resultado.consulta_db_id)
    assert leido is not None
    assert leido.estado == "ok"
    assert leido.modo == "DOCUMENTO"
    assert leido.resultado_runt is not None
    assert leido.resultado_runt.nombre == "E2E Documento"
    assert leido.resultado_runt.raw_html == "<html id='runt-e2e'>ok</html>"
    assert leido.resultado_simit is not None
    assert leido.resultado_simit.raw_html == "<html id='simit-e2e'>ok</html>"
    assert leido.resultado_simit.resumen is not None
    assert leido.resultado_simit.resumen.sin_pendientes is True
    assert len(repo.listar_eventos(resultado.consulta_db_id)) >= 1


def test_e2e_02_documento_parcial_una_fuente_falla(repo: ConsultaRepository) -> None:
    """Escenario 2: RUNT OK + SIMIT error → estado parcial y ambos rastros."""
    controller = ConsultaController()
    controller._runt.consultar_ciudadano = MagicMock(  # type: ignore[method-assign]
        return_value=ResultadoRunt(
            nombre="Parcial RUNT",
            raw_html="<runt/>",
            secciones={"LICENCIAS": []},
        )
    )
    controller._simit.consultar = MagicMock(  # type: ignore[method-assign]
        return_value=ResultadoSimit(error="SIMIT: timeout de prueba E2E")
    )

    resultado = controller.consultar(
        ConsultaParams(
            modo="DOCUMENTO",
            identificador="2222222222",
            tipo_documento="CC",
        ),
        resolver_captcha=lambda _b: "x",
        debug=False,
    )

    assert resultado.estado_global == "parcial"
    assert resultado.persistido is True
    assert resultado.consulta_db_id is not None

    leido = repo.obtener_por_id(resultado.consulta_db_id)
    assert leido is not None
    assert leido.estado == "parcial"
    assert leido.error_simit
    assert leido.resultado_runt is not None
    assert leido.resultado_runt.nombre == "Parcial RUNT"
    assert leido.resultado_simit is not None
    assert leido.resultado_simit.error
    assert "timeout" in (leido.resultado_simit.error or "").lower()


def test_e2e_03_placa_ok_solo_simit(repo: ConsultaRepository) -> None:
    """Escenario 3: PLACA → solo SIMIT; sin fila RUNT."""
    controller = ConsultaController()
    controller._simit.consultar = MagicMock(  # type: ignore[method-assign]
        return_value=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="ABC123",
                modo="PLACA",
                comparendos=0,
                sin_pendientes=True,
            ),
            raw_html="<placa/>",
        )
    )

    resultado = controller.consultar(
        ConsultaParams(modo="PLACA", identificador="ABC123"),
        debug=False,
    )

    assert resultado.estado_fuente_runt() == "omitido"
    assert resultado.estado_global == "ok"
    assert resultado.persistido is True
    assert resultado.consulta_db_id is not None

    leido = repo.obtener_por_id(resultado.consulta_db_id)
    assert leido is not None
    assert leido.modo == "PLACA"
    assert leido.resultado_runt is None
    assert leido.resultado_simit is not None
    assert leido.resultado_simit.raw_html == "<placa/>"

    with repo._db.connection() as conn:
        n_runt = conn.execute(
            "select count(*) as n from public.resultados_runt where consulta_id = %(id)s",
            {"id": resultado.consulta_db_id},
        ).fetchone()
    assert n_runt is not None
    assert int(n_runt["n"]) == 0


def test_e2e_04_fallo_persistencia_conserva_resultados() -> None:
    """Escenario 4: DSN inválido → error_persistencia; hechos en memoria OK."""
    resultado = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador="3333333333",
        tipo_documento="CC",
        correlation_id="e2e-fail-db",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(nombre="Sin BD", raw_html="<x/>"),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="3333333333",
                modo="DOCUMENTO",
                sin_pendientes=True,
            )
        ),
    )
    resultado.finalizar()

    settings = _settings_ok(
        database_url="postgresql://postgres:postgres@127.0.0.1:1/postgres",
        db_connect_timeout_s=1,
    )
    # Sin repository inyectado: fuerza intento real de conexión fallida.
    intentar_persistir_resultado(resultado, settings=settings)

    assert resultado.persistido is False
    assert resultado.consulta_db_id is None
    assert resultado.error_persistencia
    assert resultado.resultado_runt is not None
    assert resultado.resultado_runt.nombre == "Sin BD"
    assert resultado.resultado_simit is not None


def test_e2e_json_y_raw_html_en_postgres(repo: ConsultaRepository) -> None:
    """Confirma tipos JSONB + raw_html en filas reales."""
    resultado = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador="4444444444",
        tipo_documento="CC",
        correlation_id="e2e-json",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(
            nombre="JSON",
            secciones={"MULTAS E INFRACCIONES": [{"N": "1"}]},
            raw_html="<raw-runt/>",
            tiene_multas_inferidas=True,
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="4444444444",
                modo="DOCUMENTO",
                comparendos=1,
            ),
            comparendos_multas=[],
            datos_raw={"fuente": "e2e"},
            raw_html="<raw-simit/>",
        ),
    )
    resultado.finalizar()
    intentar_persistir_resultado(resultado, settings=_settings_ok(), repository=repo)

    assert resultado.consulta_db_id is not None
    with repo._db.connection() as conn:
        row = conn.execute(
            """
            select
              pg_typeof(r.secciones)::text as t_secciones,
              pg_typeof(s.resumen)::text as t_resumen,
              pg_typeof(s.comparendos_multas)::text as t_comp,
              r.raw_html as raw_runt,
              s.raw_html as raw_simit,
              r.tiene_multas_inferidas
            from public.resultados_runt r
            join public.resultados_simit s on s.consulta_id = r.consulta_id
            where r.consulta_id = %(id)s
            """,
            {"id": resultado.consulta_db_id},
        ).fetchone()

    assert row is not None
    assert "json" in row["t_secciones"]
    assert "json" in row["t_resumen"]
    assert "json" in row["t_comp"]
    assert row["raw_runt"] == "<raw-runt/>"
    assert row["raw_simit"] == "<raw-simit/>"
    assert row["tiene_multas_inferidas"] is True
