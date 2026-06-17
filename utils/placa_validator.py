# utils/placa_validator.py
"""Validación de placas vehiculares colombianas."""

import re

# AAA123 | AAA12B | DA1234 | R12345 | T1234
_PATRON_PLACA = re.compile(
    r"^("
    r"[A-Z]{3}\d{3}|"
    r"[A-Z]{3}\d{2}[A-Z]|"
    r"[A-Z]{2}\d{4}|"
    r"[A-Z]\d{5}|"
    r"[A-Z]\d{4}"
    r")$",
    re.IGNORECASE,
)

MENSAJE_PLACA_INVALIDA = (
    "La placa no tiene un formato válido.\n\n"
    "Formatos permitidos:\n"
    "• AAA123 (ej: ABC123, CYP054)\n"
    "• AAA12B (ej: ABC12D)\n"
    "• DA1234 (2 letras + 4 números)\n"
    "• R12345 (1 letra + 5 números)\n"
    "• T1234 (1 letra + 4 números)"
)


def normalizar_placa(texto: str) -> str:
    return re.sub(r"[\s\-]", "", texto.strip().upper())


def es_placa_valida(texto: str) -> bool:
    return bool(_PATRON_PLACA.match(normalizar_placa(texto)))
