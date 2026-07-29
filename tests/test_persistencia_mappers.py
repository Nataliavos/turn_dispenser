"""Tests unitarios de mappers de persistencia (sin BD)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from repositories.mappers import (
    debe_persistir_runt,
    debe_persistir_simit,
    estado_consulta_a_db,
    estado_fuente_a_db,
    fila_runt_desde_resultado,
    fila_simit_desde_resultado,
    resultado_runt_desde_fila,
    resultado_simit_desde_fila,
    to_jsonable,
)


class EstadoMapperTests(unittest.TestCase):
    def test_fuente_sin_registro_a_ok(self) -> None:
        self.assertEqual(estado_fuente_a_db("sin_registro"), "ok")
        self.assertEqual(estado_fuente_a_db("sin_pendientes"), "ok")
        self.assertEqual(estado_fuente_a_db("error"), "error")

    def test_consulta_en_progreso(self) -> None:
        r = ResultadoConsulta(modo="DOCUMENTO", identificador="1", tipo_documento="CC")
        self.assertEqual(estado_consulta_a_db(r), "en_progreso")

    def test_consulta_ok(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1",
            tipo_documento="CC",
            resultado_runt=ResultadoRunt(nombre="A"),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="1", modo="DOCUMENTO", sin_pendientes=True
                )
            ),
        )
        r.finalizar()
        self.assertEqual(estado_consulta_a_db(r), "ok")


class DebePersistirTests(unittest.TestCase):
    def test_placa_no_runt(self) -> None:
        r = ResultadoConsulta(modo="PLACA", identificador="ABC123")
        self.assertFalse(debe_persistir_runt(r))
        self.assertFalse(debe_persistir_simit(r))

    def test_error_simit_sin_objeto(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1",
            tipo_documento="CC",
            error_simit="SIMIT: caído",
        )
        self.assertTrue(debe_persistir_simit(r))


class FilaRoundtripTests(unittest.TestCase):
    def test_runt_roundtrip(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="101",
            tipo_documento="CC",
            resultado_runt=ResultadoRunt(
                nombre="Ana",
                tiene_multas_inferidas=False,
                secciones={"LICENCIAS": []},
                raw_html="<b>x</b>",
            ),
        )
        fila = fila_runt_desde_resultado(r)
        back = resultado_runt_desde_fila(fila)
        self.assertEqual(back.nombre, "Ana")
        self.assertEqual(back.raw_html, "<b>x</b>")
        self.assertEqual(back.secciones, {"LICENCIAS": []})

    def test_simit_roundtrip(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="101",
            tipo_documento="CC",
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="101",
                    modo="DOCUMENTO",
                    comparendos=1,
                    sin_pendientes=False,
                ),
            ),
        )
        fila = fila_simit_desde_resultado(r)
        self.assertIsInstance(to_jsonable(fila["resumen"]), dict)
        back = resultado_simit_desde_fila(fila)
        assert back.resumen is not None
        self.assertEqual(back.resumen.comparendos, 1)

    def test_duracion_en_consulta_ok(self) -> None:
        inicio = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
        fin = datetime(2026, 7, 29, 12, 0, 2, tzinfo=timezone.utc)
        r = ResultadoConsulta(
            modo="PLACA",
            identificador="ABC123",
            iniciado_en=inicio,
            resultado_simit=ResultadoSimit(sin_registro=True),
        )
        r.finalizar(fin)
        self.assertEqual(estado_consulta_a_db(r), "ok")


if __name__ == "__main__":
    unittest.main()
