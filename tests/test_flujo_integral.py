"""
Pruebas integrales del flujo (E-02) sin abrir Chromium ni portales.

Cubre entrada → orquestación (mock) → formateo → sugerencias de recuperación
y ausencia de lógica de elegibilidad. La persistencia real se valida en
``tests/test_persistencia_e2e.py`` (D-04) / ``docs/VALIDACION_PERSISTENCIA.md``.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from controllers.consulta_controller import ConsultaController
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit, ResumenSimit
from utils.documento_validator import validar_documento
from utils.placa_validator import es_placa_valida, normalizar_placa
from views.resultado_formatter import (
    formatear_resultado_consulta,
    mensajes_recuperacion,
    resumen_estados_consulta,
)

_FRASES_DECISION_TRAMITE = (
    "apto para trámite",
    "no apto",
    "puede tramitar",
    "puede_tramitar",
    "es elegible",
    "dictamen",
)


def _assert_sin_decision_tramite(texto: str) -> None:
    bajo = texto.lower()
    for frase in _FRASES_DECISION_TRAMITE:
        assert frase not in bajo, f"Mensaje de decisión de trámite hallado: {frase!r}"
    # La frase «no elegibilidad» en heurística RUNT es disclaimer permitido.
    assert "apto/no apto" not in bajo
    assert "resultado: apto" not in bajo


class ValidacionEntradaIntegralTests(unittest.TestCase):
    def test_documento_valido_e_invalido(self) -> None:
        ok, tipo, num, _ = validar_documento("CC", "1017259440")
        self.assertTrue(ok)
        self.assertEqual(tipo, "CC")
        self.assertEqual(num, "1017259440")

        ok2, _, _, msg = validar_documento("XX", "123")
        self.assertFalse(ok2)
        self.assertTrue(msg)

    def test_placa_valida_e_invalida(self) -> None:
        self.assertTrue(es_placa_valida(normalizar_placa("abc123")))
        self.assertFalse(es_placa_valida(normalizar_placa("XXX")))


@patch("controllers.consulta_controller.intentar_persistir_resultado")
class FlujoDocumentoIntegralTests(unittest.TestCase):
    def test_documento_ok_progreso_y_formateo(self, _persist: MagicMock) -> None:
        ctrl = ConsultaController()
        ctrl._runt = MagicMock()
        ctrl._simit = MagicMock()
        ctrl._runt.consultar_ciudadano.return_value = ResultadoRunt(
            nombre="Integral Doc",
            estado_licencia="ACTIVO",
            raw_html="<html>runt</html>",
        )
        ctrl._simit.consultar.return_value = ResultadoSimit(
            resumen=ResumenSimit(
                identificador="1017",
                modo="DOCUMENTO",
                sin_pendientes=True,
            ),
            raw_html="<html>simit</html>",
        )

        eventos: list[tuple[str, str]] = []
        out = ctrl.consultar(
            ConsultaParams(
                modo="DOCUMENTO",
                identificador="1017",
                tipo_documento="CC",
            ),
            debug=False,
            on_progreso=lambda f, e: eventos.append((f, e)),
        )

        self.assertEqual(out.estado_global, "ok")
        self.assertIsNotNone(out.correlation_id)
        self.assertIn(("RUNT", "en_curso"), eventos)
        self.assertIn(("SIMIT", "en_curso"), eventos)
        self.assertEqual(out.estado_fuente_runt(), "ok")
        self.assertEqual(out.estado_fuente_simit(), "sin_pendientes")

        lineas: list[str] = []
        formatear_resultado_consulta(out, lineas.append)
        texto = "\n".join(lineas)
        self.assertIn("RUNT", texto)
        self.assertIn("SIMIT", texto)
        _assert_sin_decision_tramite(texto)
        self.assertEqual(mensajes_recuperacion(out), [])

    def test_documento_parcial_recuperacion_sin_elegibilidad(
        self, _persist: MagicMock
    ) -> None:
        ctrl = ConsultaController()
        ctrl._runt = MagicMock()
        ctrl._simit = MagicMock()
        ctrl._runt.consultar_ciudadano.return_value = ResultadoRunt(
            nombre="Parcial",
            raw_html="<html>runt</html>",
        )
        ctrl._simit.consultar.return_value = ResultadoSimit(
            error="SIMIT: tiempo de espera agotado. Acción: reintenta.",
        )

        out = ctrl.consultar(
            ConsultaParams(
                modo="DOCUMENTO",
                identificador="1017",
                tipo_documento="CC",
            ),
            debug=False,
        )
        self.assertEqual(out.estado_global, "parcial")
        self.assertIn("SIMIT", resumen_estados_consulta(out))

        msgs = mensajes_recuperacion(out)
        self.assertTrue(msgs)
        unidos = " ".join(msgs)
        self.assertIn("SIMIT", unidos)
        self.assertIn("Reintentar consulta", unidos)

        lineas: list[str] = []
        formatear_resultado_consulta(out, lineas.append)
        texto = "\n".join(lineas)
        _assert_sin_decision_tramite(texto)
        self.assertTrue(any("reintentar consulta" in x.lower() for x in lineas))
        self.assertIn("no elegibilidad", texto.lower())  # disclaimer RUNT permitido


@patch("controllers.consulta_controller.intentar_persistir_resultado")
class FlujoPlacaIntegralTests(unittest.TestCase):
    def test_placa_ok_sin_runt(self, _persist: MagicMock) -> None:
        ctrl = ConsultaController()
        ctrl._runt = MagicMock()
        ctrl._simit = MagicMock()
        ctrl._simit.consultar.return_value = ResultadoSimit(
            resumen=ResumenSimit(
                identificador="ABC123",
                modo="PLACA",
                sin_pendientes=True,
            ),
            raw_html="<html>simit</html>",
        )

        eventos: list[tuple[str, str]] = []
        out = ctrl.consultar(
            ConsultaParams(modo="PLACA", identificador="ABC123"),
            debug=False,
            on_progreso=lambda f, e: eventos.append((f, e)),
        )

        self.assertEqual(out.estado_global, "ok")
        self.assertEqual(out.estado_fuente_runt(), "omitido")
        self.assertEqual(out.estado_fuente_simit(), "sin_pendientes")
        ctrl._runt.consultar_ciudadano.assert_not_called()
        self.assertIn(("RUNT", "omitido"), eventos)

        lineas: list[str] = []
        formatear_resultado_consulta(out, lineas.append)
        texto = "\n".join(lineas)
        self.assertNotIn("══════════ RUNT ══════════", texto)


class AusenciaElegibilidadIntegralTests(unittest.TestCase):
    def test_modelos_sin_campos_de_tramite(self) -> None:
        r = ResultadoConsulta(modo="DOCUMENTO", identificador="1")
        for attr in ("apto", "puede_tramitar", "elegible", "dictamen"):
            self.assertFalse(hasattr(r, attr))
        runt = ResultadoRunt(nombre="X", tiene_multas_inferidas=True)
        self.assertTrue(hasattr(runt, "tiene_multas_inferidas"))
        self.assertFalse(hasattr(runt, "puede_tramitar"))


if __name__ == "__main__":
    unittest.main()
