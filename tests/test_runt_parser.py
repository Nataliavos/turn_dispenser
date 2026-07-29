"""Tests offline de ``parse_runt_html`` (C-02)."""

from __future__ import annotations

from models.runt_models import inferir_multas_desde_secciones
from services.runt_parser import parse_runt_html
from tests.conftest import load_fixture


def test_runt_ok_extrae_campos_criticos() -> None:
    html = load_fixture("runt", "ok_con_datos.html")
    parsed = parse_runt_html(html)

    assert parsed["nombre_completo"] == "PERSONA DE PRUEBA FICTICIA"
    assert parsed["tipo_documento"] == "CC"
    assert parsed["numero_documento"] == "1000000001"
    assert parsed["estado_persona"] == "ACTIVO"
    assert parsed["estado_conductor"] == "ACTIVO"
    assert parsed["numero_inscripcion"] == "999000111"
    assert parsed["fecha_inscripcion"] == "01/01/2020"

    secciones = parsed["secciones"]
    assert "LICENCIAS" in secciones
    assert isinstance(secciones["LICENCIAS"], list)
    assert secciones["LICENCIAS"][0]["NÚMERO"] == "LIC-0001"
    assert secciones["LICENCIAS"][0]["CATEGORÍA"] == "B1"

    assert "MULTAS E INFRACCIONES" in secciones
    assert isinstance(secciones["MULTAS E INFRACCIONES"], list)
    assert len(secciones["MULTAS E INFRACCIONES"]) == 1
    assert inferir_multas_desde_secciones(secciones) is True

    assert "VALIDACIÓN" in secciones
    assert secciones["VALIDACIÓN"]["INDICADOR DE ESTADO CIUDADANO"] == "VALIDADO"


def test_runt_vacio_degrada_sin_campos() -> None:
    html = load_fixture("runt", "vacio.html")
    parsed = parse_runt_html(html)

    assert parsed["nombre_completo"] is None
    assert parsed["tipo_documento"] is None
    assert parsed["numero_documento"] is None
    assert parsed["estado_conductor"] is None
    assert parsed["secciones"] == {}
    assert inferir_multas_desde_secciones(parsed["secciones"]) is False
