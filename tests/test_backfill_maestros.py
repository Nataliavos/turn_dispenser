"""Tests unitarios del backfill F-06 (sin BD / con mocks)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from models.runt_models import ResultadoRunt
from models.simit_models import ComparendoMulta, ResultadoSimit, ResumenSimit
from repositories.backfill import ejecutar_backfill
from repositories.backfill_helpers import (
    describir_plan_backfill,
    resultado_consulta_desde_registro,
    tiene_snapshot_util,
)
from repositories.consulta_repository import ConsultaRegistro
from repositories.exceptions import PersistenciaError


def _reg(**overrides) -> ConsultaRegistro:
    base = dict(
        id=uuid4(),
        correlation_id="cid-bf",
        modo="DOCUMENTO",
        identificador="1234567890",
        tipo_documento="CC",
        estado="ok",
        schema_version="2",
        iniciado_en=datetime.now(timezone.utc),
        finalizado_en=datetime.now(timezone.utc),
        error_runt=None,
        error_simit=None,
        resultado_runt=ResultadoRunt(
            nombre="Backfill",
            tipo_documento="CC",
            numero_documento="1234567890",
            raw_html="<r/>",
        ),
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="1234567890",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
            raw_html="<s/>",
        ),
    )
    base.update(overrides)
    return ConsultaRegistro(**base)


def test_resultado_desde_registro_reconstruye_contrato() -> None:
    reg = _reg()
    r = resultado_consulta_desde_registro(reg)
    assert r.modo == "DOCUMENTO"
    assert r.identificador == "1234567890"
    assert r.consulta_db_id == reg.id
    assert r.persistido is True
    assert r.resultado_runt is not None
    assert r.resultado_runt.nombre == "Backfill"
    assert r.estado_global == "ok"


def test_describir_plan_documento_y_omitida_sin_snapshot() -> None:
    desc = describir_plan_backfill(_reg())
    assert not desc.omitida
    assert any("persona upsert CC/1234567890" in line for line in desc.lineas)

    vacio = _reg(resultado_runt=None, resultado_simit=None)
    assert not tiene_snapshot_util(vacio)
    desc2 = describir_plan_backfill(vacio)
    assert desc2.omitida


def test_describir_plan_placa_y_obligaciones() -> None:
    reg = _reg(
        modo="PLACA",
        identificador="ABC123",
        tipo_documento=None,
        resultado_runt=None,
        resultado_simit=ResultadoSimit(
            resumen=ResumenSimit(
                identificador="ABC123",
                modo="PLACA",
                sin_pendientes=False,
                comparendos=1,
            ),
            comparendos_multas=[
                ComparendoMulta(numero="N1", placa="ABC123", valor="1000")
            ],
        ),
    )
    desc = describir_plan_backfill(reg)
    assert any("vehiculo upsert ABC123" in line for line in desc.lineas)
    assert any("obligaciones_simit: 1" in line for line in desc.lineas)


def test_ejecutar_backfill_dry_run_no_escribe() -> None:
    cid = uuid4()
    reg = _reg(id=cid)
    repo = MagicMock()
    repo.listar_consultas_para_backfill.return_value = [cid]
    repo.obtener_por_id.return_value = reg

    resumen = ejecutar_backfill(repo, dry_run=True)
    assert resumen.procesadas == 1
    assert resumen.errores == 0
    repo.normalizar_maestros_y_hechos.assert_not_called()


def test_ejecutar_backfill_real_y_error_por_fila() -> None:
    ok_id = uuid4()
    fail_id = uuid4()
    repo = MagicMock()
    repo.listar_consultas_para_backfill.return_value = [ok_id, fail_id]
    repo.obtener_por_id.side_effect = [
        _reg(id=ok_id),
        _reg(id=fail_id, correlation_id="cid-fail"),
    ]
    repo.normalizar_maestros_y_hechos.side_effect = [
        {"persona_id": uuid4(), "vehiculo_id": None},
        PersistenciaError("boom"),
    ]

    resumen = ejecutar_backfill(repo, dry_run=False)
    assert resumen.procesadas == 1
    assert resumen.errores == 1
    assert resumen.candidatas == 2
    assert any("boom" in e for e in resumen.detalle_errores)
