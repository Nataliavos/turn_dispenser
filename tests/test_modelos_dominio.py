"""Tests del contrato de modelos de dominio (C-01)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from models.consulta_models import ResultadoConsulta
from models.runt_models import (
    SCHEMA_VERSION_RUNT,
    ResultadoRunt,
    inferir_multas_desde_secciones,
)
from models.simit_models import SCHEMA_VERSION_SIMIT, ResultadoSimit, ResumenSimit


class SchemaVersionTests(unittest.TestCase):
    def test_defaults(self) -> None:
        self.assertEqual(ResultadoRunt().schema_version, SCHEMA_VERSION_RUNT)
        self.assertEqual(ResultadoSimit().schema_version, SCHEMA_VERSION_SIMIT)


class InferirMultasTests(unittest.TestCase):
    def test_sin_seccion(self) -> None:
        self.assertFalse(inferir_multas_desde_secciones({}))

    def test_lista_vacia(self) -> None:
        self.assertFalse(
            inferir_multas_desde_secciones({"MULTAS E INFRACCIONES": []})
        )

    def test_lista_con_filas(self) -> None:
        self.assertTrue(
            inferir_multas_desde_secciones(
                {"MULTAS E INFRACCIONES": [{"NUMERO": "1"}]}
            )
        )


class EstadoGlobalTests(unittest.TestCase):
    def test_ok_documento(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1",
            resultado_runt=ResultadoRunt(nombre="Ana"),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="1",
                    modo="DOCUMENTO",
                    sin_pendientes=True,
                ),
            ),
        )
        self.assertEqual(r.calcular_estado_global(), "ok")

    def test_parcial(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1",
            resultado_runt=ResultadoRunt(nombre="Ana"),
            error_simit="SIMIT: fallo",
            resultado_simit=ResultadoSimit(error="SIMIT: fallo"),
        )
        self.assertEqual(r.calcular_estado_global(), "parcial")

    def test_error(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1",
            error_runt="RUNT: fallo",
            resultado_runt=ResultadoRunt(error="RUNT: fallo"),
            error_simit="SIMIT: fallo",
            resultado_simit=ResultadoSimit(error="SIMIT: fallo"),
        )
        self.assertEqual(r.calcular_estado_global(), "error")

    def test_finalizar_congela_metadatos(self) -> None:
        inicio = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
        fin = datetime(2026, 7, 29, 12, 1, tzinfo=timezone.utc)
        r = ResultadoConsulta(modo="PLACA", identificador="ABC123")
        r.marcar_inicio(correlation_id="abc123def456", momento=inicio)
        r.resultado_simit = ResultadoSimit(
            resumen=ResumenSimit(
                identificador="ABC123",
                modo="PLACA",
                sin_pendientes=True,
            ),
        )
        r.finalizar(momento=fin)
        self.assertEqual(r.correlation_id, "abc123def456")
        self.assertEqual(r.iniciado_en, inicio)
        self.assertEqual(r.finalizado_en, fin)
        self.assertEqual(r.estado_global, "ok")


class CampoDerivadoTests(unittest.TestCase):
    def test_tiene_multas_inferidas_no_es_elegibilidad(self) -> None:
        # Campo presente y tipado; semántica documentada como heurística.
        r = ResultadoRunt(tiene_multas_inferidas=True)
        self.assertTrue(hasattr(r, "tiene_multas_inferidas"))
        self.assertFalse(hasattr(r, "puede_tramitar"))
        self.assertFalse(hasattr(r, "elegible"))


if __name__ == "__main__":
    unittest.main()
