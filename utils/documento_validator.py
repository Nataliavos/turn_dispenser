"""Validación básica de tipo + número de documento (RF-03).

Heurísticas conservadoras para reducir consultas inválidas antes de Playwright.
No valida existencia real en RUNT/SIMIT.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# Tipos alineados con la GUI y el mapa RUNT activo.
TIPOS_SOPORTADOS: frozenset[str] = frozenset(
    {"CC", "CE", "TI", "RC", "PPT", "CD", "PA"}
)

# Tipos cuyo número debe ser solo dígitos tras normalizar.
_TIPOS_SOLO_DIGITOS: frozenset[str] = frozenset({"CC", "TI", "RC"})

# Longitud mínima/máxima por tipo (tras normalizar). Heurística documentada.
_LONGITUD_POR_TIPO: dict[str, Tuple[int, int]] = {
    "CC": (5, 12),
    "TI": (5, 12),
    "RC": (5, 12),
    "CE": (3, 20),
    "PPT": (3, 20),
    "PA": (5, 20),
    "CD": (3, 20),
}

_PATRON_DIGITOS = re.compile(r"^\d+$")
_PATRON_ALNUM = re.compile(r"^[A-Z0-9]+$")

MENSAJE_TIPOS_SOPORTADOS = (
    "Tipos soportados: "
    + ", ".join(sorted(TIPOS_SOPORTADOS))
    + "."
)


def normalizar_tipo_documento(tipo: str) -> str:
    """Normaliza el código de tipo (mayúsculas, sin espacios)."""
    return (tipo or "").strip().upper()


def normalizar_numero_documento(numero: str) -> str:
    """Quita espacios, puntos y guiones; deja el resto en mayúsculas."""
    limpio = re.sub(r"[\s.\-]", "", (numero or "").strip())
    return limpio.upper()


def es_documento_valido(tipo: str, numero: str) -> bool:
    ok, _, _, _ = validar_documento(tipo, numero)
    return ok


def validar_documento(
    tipo: str,
    numero: str,
) -> Tuple[bool, str, str, str]:
    """
    Valida tipo + número de documento.

    Returns:
        (ok, tipo_normalizado, numero_normalizado, mensaje_error).
        Si ok es True, mensaje_error es cadena vacía.
    """
    tipo_norm = normalizar_tipo_documento(tipo)
    numero_norm = normalizar_numero_documento(numero)

    if not tipo_norm:
        return False, tipo_norm, numero_norm, (
            "Debes indicar el tipo de documento.\n\n" + MENSAJE_TIPOS_SOPORTADOS
        )

    if tipo_norm not in TIPOS_SOPORTADOS:
        return False, tipo_norm, numero_norm, (
            f"Tipo de documento no soportado: '{tipo_norm}'.\n\n"
            + MENSAJE_TIPOS_SOPORTADOS
        )

    if not numero_norm:
        return False, tipo_norm, numero_norm, (
            "Debes ingresar el número de documento."
        )

    min_len, max_len = _LONGITUD_POR_TIPO[tipo_norm]
    if len(numero_norm) < min_len or len(numero_norm) > max_len:
        return False, tipo_norm, numero_norm, (
            f"El número de documento para {tipo_norm} debe tener entre "
            f"{min_len} y {max_len} caracteres "
            f"(ingresaste {len(numero_norm)})."
        )

    if tipo_norm in _TIPOS_SOLO_DIGITOS:
        if not _PATRON_DIGITOS.match(numero_norm):
            return False, tipo_norm, numero_norm, (
                f"El número de {tipo_norm} solo puede contener dígitos "
                "(sin letras ni símbolos)."
            )
    else:
        if not _PATRON_ALNUM.match(numero_norm):
            return False, tipo_norm, numero_norm, (
                f"El número de {tipo_norm} solo puede contener letras y dígitos "
                "(sin símbolos)."
            )

    return True, tipo_norm, numero_norm, ""


def mensaje_documento_invalido(
    tipo: str,
    numero: str,
    mensaje: Optional[str] = None,
) -> str:
    """Mensaje de error listo para mostrar al operador."""
    if mensaje:
        return mensaje
    ok, _, _, msg = validar_documento(tipo, numero)
    if ok:
        return ""
    return msg
