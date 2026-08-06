"""Tests unitarios de mappers de normalización v2 (sin BD)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import (
    AcuerdoPago,
    ComparendoMulta,
    ResultadoSimit,
    ResumenSimit,
)
from repositories.normalizacion_mappers import (
    fingerprint,
    parse_monto_numeric,
    plan_normalizacion_desde_resultado,
)


class ParseMontoTests(unittest.TestCase):
    def test_formato_col(self) -> None:
        self.assertEqual(parse_monto_numeric("$ 604.100"), Decimal("604100"))
        self.assertEqual(parse_monto_numeric("1.234,50"), Decimal("1234.50"))

    def test_invalido(self) -> None:
        self.assertIsNone(parse_monto_numeric(None))
        self.assertIsNone(parse_monto_numeric("N/A"))


class FingerprintTests(unittest.TestCase):
    def test_estable(self) -> None:
        a = fingerprint("A", "b", None)
        b = fingerprint("a", "B", "")
        self.assertEqual(a, b)


class PlanDocumentoTests(unittest.TestCase):
    def test_documento_persona_licencia_infraccion(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="1000000001",
            tipo_documento="CC",
            resultado_runt=ResultadoRunt(
                nombre="Ana Prueba",
                tipo_documento="CC",
                numero_documento="1000000001",
                estado_persona="ACTIVO",
                numero_inscripcion="999",
                fecha_inscripcion="01/01/2020",
                secciones={
                    "LICENCIAS": [
                        {
                            "NÚMERO": "LIC-0001",
                            "CATEGORÍA": "B1",
                            "ESTADO": "ACTIVA",
                        }
                    ],
                    "MULTAS E INFRACCIONES": [
                        {
                            "NÚMERO": "MUL-0001",
                            "DESCRIPCIÓN": "Infracción de prueba",
                            "ESTADO": "PENDIENTE",
                        }
                    ],
                },
            ),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="1000000001",
                    modo="DOCUMENTO",
                    comparendos=1,
                    sin_pendientes=False,
                ),
                comparendos_multas=[
                    ComparendoMulta(
                        numero="CMP-1",
                        tipo="comparendo",
                        placa="ABC123",
                        valor="$ 10.000",
                        estado="PENDIENTE",
                    )
                ],
            ),
        )
        plan = plan_normalizacion_desde_resultado(r)
        assert plan.persona is not None
        self.assertEqual(plan.persona.tipo_documento, "CC")
        self.assertEqual(plan.persona.numero_documento, "1000000001")
        self.assertEqual(plan.persona.nombre_completo, "Ana Prueba")
        self.assertEqual(len(plan.licencias), 1)
        self.assertEqual(plan.licencias[0].numero_licencia, "LIC-0001")
        self.assertEqual(len(plan.infracciones_runt), 1)
        self.assertEqual(len(plan.obligaciones_simit), 1)
        self.assertEqual(plan.obligaciones_simit[0].numero, "CMP-1")
        self.assertEqual(plan.obligaciones_simit[0].valor, Decimal("10000"))
        placas = {v.placa for v in plan.vehiculos}
        self.assertIn("ABC123", placas)
        self.assertTrue(any(v.placa == "ABC123" for v in plan.vinculos))


class PlanPlacaTests(unittest.TestCase):
    def test_placa_vehiculo_y_tipo_documento_null_en_consulta(self) -> None:
        r = ResultadoConsulta(
            modo="PLACA",
            identificador="xyz-999",
            tipo_documento=None,
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="XYZ999",
                    modo="PLACA",
                    cedula="12345678",
                    comparendos=1,
                    sin_pendientes=False,
                ),
                comparendos_multas=[
                    ComparendoMulta(
                        numero="OB-9",
                        placa="XYZ999",
                        tipo="multa",
                        valor="5000",
                    )
                ],
            ),
        )
        self.assertIsNone(r.tipo_documento)
        self.assertEqual(r.modo, "PLACA")
        plan = plan_normalizacion_desde_resultado(r)
        self.assertEqual({v.placa for v in plan.vehiculos}, {"XYZ999"})
        assert plan.persona is not None
        self.assertEqual(plan.persona.numero_documento, "12345678")
        self.assertEqual(plan.persona.tipo_documento, "CC")
        self.assertEqual(len(plan.obligaciones_simit), 1)
        self.assertTrue(plan.vinculos)


class PlanSinPendientesTests(unittest.TestCase):
    def test_sin_pendientes_cero_obligaciones(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="101",
            tipo_documento="CC",
            resultado_runt=ResultadoRunt(nombre="Ana"),
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="101",
                    modo="DOCUMENTO",
                    sin_pendientes=True,
                ),
                comparendos_multas=[],
                acuerdos_pago=[],
            ),
        )
        plan = plan_normalizacion_desde_resultado(r)
        assert plan.persona is not None
        self.assertEqual(plan.obligaciones_simit, [])
        self.assertEqual(plan.acuerdos_pago_simit, [])

    def test_acuerdo_mapeado(self) -> None:
        r = ResultadoConsulta(
            modo="DOCUMENTO",
            identificador="101",
            tipo_documento="cc",
            resultado_simit=ResultadoSimit(
                resumen=ResumenSimit(
                    identificador="101", modo="DOCUMENTO", sin_pendientes=False
                ),
                acuerdos_pago=[
                    AcuerdoPago(
                        numero_acuerdo="AP-1",
                        valor_acuerdo="$ 1.000",
                        pendiente="500",
                    )
                ],
            ),
        )
        plan = plan_normalizacion_desde_resultado(r)
        self.assertEqual(len(plan.acuerdos_pago_simit), 1)
        self.assertEqual(plan.acuerdos_pago_simit[0].numero_acuerdo, "AP-1")
        self.assertEqual(plan.acuerdos_pago_simit[0].valor, Decimal("1000"))


if __name__ == "__main__":
    unittest.main()
