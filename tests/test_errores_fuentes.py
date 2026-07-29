"""Tests del contrato unificado de errores por fuente (B-04)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from controllers.consulta_controller import ConsultaController
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.exceptions import FUENTE_RUNT, FUENTE_SIMIT, mensaje_accionable_fuente
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from views.resultado_formatter import (
    formatear_resultado_consulta,
    resumen_estados_consulta,
)


class MensajeAccionableTests(unittest.TestCase):
    def test_timeout(self) -> None:
        class TimeoutErrorFake(Exception):
            pass

        msg = mensaje_accionable_fuente(FUENTE_SIMIT, TimeoutErrorFake("timeout waiting"))
        self.assertIn("SIMIT", msg)
        self.assertIn("tiempo de espera", msg.lower())


class ResultadoConsultaEstadoTests(unittest.TestCase):
    def test_estados_parciales(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="123",
            resultado_runt=ResultadoRunt(nombre="Ana"),
            error_simit="SIMIT: fallo de red",
            resultado_simit=ResultadoSimit(error="SIMIT: fallo de red"),
        )
        self.assertEqual(r.estado_fuente_runt(), "ok")
        self.assertEqual(r.estado_fuente_simit(), "error")
        self.assertIn("RUNT: OK", resumen_estados_consulta(r))
        self.assertIn("SIMIT: error", resumen_estados_consulta(r))

    def test_simit_sin_pendientes(self) -> None:
        r = ResultadoConsulta(
            modo="PLACA",
            identificador="ABC123",
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="ABC123",
                    modo="PLACA",
                    sin_pendientes=True,
                ),
            ),
        )
        self.assertEqual(r.estado_fuente_simit(), "sin_pendientes")
        self.assertEqual(r.estado_fuente_runt(), "omitido")


class ConsultaControllerAislamientoTests(unittest.TestCase):
    def test_falla_simit_no_tumba_runt(self) -> None:
        ctrl = ConsultaController()
        ctrl._runt = MagicMock()
        ctrl._simit = MagicMock()
        ctrl._runt.consultar_ciudadano.return_value = ResultadoRunt(nombre="Ana")
        ctrl._simit.consultar.return_value = ResultadoSimit(
            error="SIMIT: tiempo de espera agotado."
        )

        out = ctrl.consultar(
            ConsultaParams(modo="DOCUMENTO", identificador="1017", tipo_documento="CC"),
            debug=False,
        )
        self.assertIsNone(out.error_runt)
        self.assertEqual(out.resultado_runt.nombre, "Ana")
        self.assertIsNotNone(out.error_simit)
        self.assertIn("SIMIT", out.error_simit)

    def test_falla_runt_no_tumba_simit(self) -> None:
        ctrl = ConsultaController()
        ctrl._runt = MagicMock()
        ctrl._simit = MagicMock()
        ctrl._runt.consultar_ciudadano.return_value = ResultadoRunt(
            error="RUNT: tiempo de espera agotado."
        )
        ctrl._simit.consultar.return_value = ResultadoSimit(
            resumen=ResumenSimit(
                identificador="1017",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
        )

        out = ctrl.consultar(
            ConsultaParams(modo="DOCUMENTO", identificador="1017", tipo_documento="CC"),
            debug=False,
        )
        self.assertIsNotNone(out.error_runt)
        self.assertIsNone(out.error_simit)
        self.assertEqual(out.estado_fuente_simit(), "sin_pendientes")


class FormatterSimetriaTests(unittest.TestCase):
    def test_errores_simetricos(self) -> None:
        lineas: list[str] = []
        formatear_resultado_consulta(
            ResultadoConsulta(
                modo="DOCUMENTO",
                identificador="1",
                error_runt="RUNT: fallo",
                error_simit="SIMIT: fallo",
            ),
            lineas.append,
        )
        self.assertTrue(any("Error RUNT" in x for x in lineas))
        self.assertTrue(any("Error SIMIT" in x for x in lineas))


if __name__ == "__main__":
    unittest.main()
