"""Tests mínimos del validador de documento (stdlib unittest)."""

from __future__ import annotations

import unittest

from utils.documento_validator import (
    TIPOS_SOPORTADOS,
    es_documento_valido,
    normalizar_numero_documento,
    normalizar_tipo_documento,
    validar_documento,
)


class DocumentoValidatorTests(unittest.TestCase):
    def test_normalizacion(self) -> None:
        self.assertEqual(normalizar_tipo_documento(" cc "), "CC")
        self.assertEqual(normalizar_numero_documento("1.017.259.440"), "1017259440")
        self.assertEqual(normalizar_numero_documento("AB-12 34"), "AB1234")

    def test_cc_valida(self) -> None:
        ok, tipo, numero, msg = validar_documento("CC", "1017259440")
        self.assertTrue(ok)
        self.assertEqual(tipo, "CC")
        self.assertEqual(numero, "1017259440")
        self.assertEqual(msg, "")
        self.assertTrue(es_documento_valido("cc", "10.172.594.40"))

    def test_vacio(self) -> None:
        ok, _, _, msg = validar_documento("CC", "   ")
        self.assertFalse(ok)
        self.assertIn("número", msg.lower())

    def test_tipo_no_soportado(self) -> None:
        ok, _, _, msg = validar_documento("NIT", "900123456")
        self.assertFalse(ok)
        self.assertIn("no soportado", msg.lower())

    def test_cc_con_letras(self) -> None:
        ok, _, _, msg = validar_documento("CC", "ABC12345")
        self.assertFalse(ok)
        self.assertIn("dígitos", msg.lower())

    def test_longitud_fuera_de_rango(self) -> None:
        ok, _, _, msg = validar_documento("CC", "12")
        self.assertFalse(ok)
        self.assertIn("entre", msg.lower())

    def test_tipos_gui_aceptados(self) -> None:
        for tipo in ("CC", "CE", "TI", "RC", "PPT", "PA", "CD"):
            self.assertIn(tipo, TIPOS_SOPORTADOS)
            self.assertTrue(es_documento_valido(tipo, "1234567890"))

    def test_ce_alfanumerico(self) -> None:
        self.assertTrue(es_documento_valido("CE", "E123456"))


if __name__ == "__main__":
    unittest.main()
