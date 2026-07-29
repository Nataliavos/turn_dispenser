"""Tests offline de ``parse_simit_html`` (C-02)."""

from __future__ import annotations

from models.simit_models import SCHEMA_VERSION_SIMIT
from services.simit_parser import parse_simit_html
from tests.conftest import load_fixture

_IDENTIFICADOR = "1000000001"
_MODO = "DOCUMENTO"


def test_simit_ok_extrae_campos_criticos() -> None:
    html = load_fixture("simit", "ok_con_datos.html")
    resultado = parse_simit_html(html, identificador=_IDENTIFICADOR, modo=_MODO)

    assert resultado.schema_version == SCHEMA_VERSION_SIMIT
    assert resultado.raw_html == html
    assert resultado.error is None
    assert resultado.sin_registro is False

    resumen = resultado.resumen
    assert resumen is not None
    assert resumen.identificador == _IDENTIFICADOR
    assert resumen.modo == _MODO
    assert resumen.cedula == _IDENTIFICADOR
    assert resumen.comparendos == 1
    assert resumen.multas == 1
    assert resumen.acuerdos_pago == 0
    assert resumen.total == "$ 250.000"
    assert resumen.sin_pendientes is False

    assert len(resultado.comparendos_multas) == 1
    item = resultado.comparendos_multas[0]
    assert item.numero == "CMP-TEST-0001"
    assert item.tipo == "Comparendo"
    assert item.fecha_imposicion == "15/03/2024"
    assert item.placa == "XYZ999"
    assert item.secretaria == "Secretaría de Prueba"
    assert item.infraccion == "C29"
    assert item.infraccion_descripcion == "Exceso de velocidad de prueba"
    assert item.estado == "Pendiente"
    assert item.valor == "$ 250.000"
    assert item.valor_a_pagar == "$ 250.000"

    assert resultado.total_comparendos_multas is not None
    assert resultado.total_comparendos_multas.cantidad == 1
    assert resultado.total_comparendos_multas.valor == "$ 250.000"
    assert resultado.acuerdos_pago == []


def test_simit_sin_pendientes() -> None:
    html = load_fixture("simit", "sin_pendientes.html")
    resultado = parse_simit_html(html, identificador=_IDENTIFICADOR, modo=_MODO)

    assert resultado.raw_html == html
    assert resultado.error is None
    assert resultado.sin_registro is False
    assert resultado.comparendos_multas == []
    assert resultado.acuerdos_pago == []

    resumen = resultado.resumen
    assert resumen is not None
    assert resumen.comparendos == 0
    assert resumen.multas == 0
    assert resumen.acuerdos_pago == 0
    assert resumen.sin_pendientes is True
    assert resumen.mensaje_estado is not None
    assert "pendientes" in resumen.mensaje_estado.lower()
