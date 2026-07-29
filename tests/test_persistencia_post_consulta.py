"""Tests de persistencia post-consulta (D-03) con repositorio mockeado."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from config.settings import Settings
from controllers.persistencia_post_consulta import intentar_persistir_resultado
from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from repositories.exceptions import ConexionPersistenciaError
from views.resultado_formatter import formatear_resultado_consulta


def _settings(**overrides: Any) -> Settings:
    base = Settings(
        app_env="local",
        debug=True,
        log_level="INFO",
        log_file=None,
        runt_url="http://runt.test",
        simit_url="http://simit.test",
        browser_headless=False,
        runt_slow_mo_ms=0,
        simit_slow_mo_ms=0,
        navigation_timeout_ms=1000,
        runt_network_idle_timeout_ms=1000,
        simit_network_idle_timeout_ms=1000,
        simit_results_timeout_ms=1000,
        runt_captcha_timeout_ms=1000,
        database_url="postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        db_connect_timeout_s=5,
        persistencia_enabled=True,
        operador="test",
        estacion="pytest",
        app_version="d03",
        supabase_url=None,
        supabase_anon_key=None,
        supabase_service_role_key=None,
    )
    return replace(base, **overrides)


def _resultado_doc() -> ResultadoConsulta:
    r = ResultadoConsulta(
        modo="DOCUMENTO",
        identificador="1",
        tipo_documento="CC",
        correlation_id="cid-test",
        iniciado_en=datetime.now(timezone.utc),
        resultado_runt=ResultadoRunt(nombre="Ana"),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="1", modo="DOCUMENTO", sin_pendientes=True
            )
        ),
    )
    r.finalizar()
    return r


def test_persistencia_omitida_por_flag() -> None:
    resultado = _resultado_doc()
    intentar_persistir_resultado(
        resultado,
        settings=_settings(persistencia_enabled=False),
        repository=MagicMock(),
    )
    assert resultado.persistencia_omitida is True
    assert resultado.persistido is None
    assert resultado.error_persistencia is None


def test_persistencia_sin_database_url() -> None:
    resultado = _resultado_doc()
    intentar_persistir_resultado(
        resultado,
        settings=_settings(database_url=None),
        repository=MagicMock(),
    )
    assert resultado.persistido is False
    assert resultado.error_persistencia is not None
    assert "DATABASE_URL" in resultado.error_persistencia


def test_persistencia_ok() -> None:
    resultado = _resultado_doc()
    consulta_id = uuid4()
    repo = MagicMock()
    repo.persistir_resultado_consulta.return_value = consulta_id

    intentar_persistir_resultado(
        resultado,
        settings=_settings(),
        repository=repo,
    )

    assert resultado.persistido is True
    assert resultado.consulta_db_id == consulta_id
    assert resultado.error_persistencia is None
    repo.persistir_resultado_consulta.assert_called_once()
    repo.agregar_evento.assert_called_once()


def test_persistencia_fallo_conexion_no_tira_resultados() -> None:
    resultado = _resultado_doc()
    repo = MagicMock()
    repo.persistir_resultado_consulta.side_effect = ConexionPersistenciaError(
        "Docker caído"
    )

    intentar_persistir_resultado(
        resultado,
        settings=_settings(),
        repository=repo,
    )

    assert resultado.persistido is False
    assert resultado.resultado_runt is not None
    assert resultado.resultado_runt.nombre == "Ana"
    assert resultado.error_persistencia is not None
    assert "Docker caído" in resultado.error_persistencia


def test_formatter_muestra_aviso_persistencia() -> None:
    resultado = _resultado_doc()
    resultado.persistido = False
    resultado.error_persistencia = "BD no disponible"
    lineas: list[str] = []
    formatear_resultado_consulta(resultado, lineas.append)
    assert any("Persistencia: no se guardó" in line for line in lineas)


def test_formatter_muestra_id_cuando_ok() -> None:
    resultado = _resultado_doc()
    resultado.persistido = True
    resultado.consulta_db_id = uuid4()
    lineas: list[str] = []
    formatear_resultado_consulta(resultado, lineas.append)
    assert any("Persistencia: guardada" in line for line in lineas)
