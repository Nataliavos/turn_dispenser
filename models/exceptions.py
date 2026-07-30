"""Errores de dominio ligeros por fuente de consulta (RUNT / SIMIT)."""

from __future__ import annotations

from typing import Optional


FUENTE_RUNT = "RUNT"
FUENTE_SIMIT = "SIMIT"


class FuenteConsultaError(Exception):
    """
    Fallo operativo de una fuente.

    No implica abortar la consulta completa: la otra fuente puede continuar.
    """

    def __init__(
        self,
        fuente: str,
        mensaje: str,
        *,
        causa: Optional[BaseException] = None,
    ) -> None:
        self.fuente = fuente.strip().upper()
        self.mensaje = mensaje.strip()
        self.causa = causa
        super().__init__(f"[{self.fuente}] {self.mensaje}")


def mensaje_accionable_fuente(fuente: str, exc: BaseException) -> str:
    """
    Traduce una excepción a mensaje orientado al operador (RF-20).

    Incluye fuente, causa probable y siguiente acción cuando es posible.
    """
    fuente_norm = fuente.strip().upper()
    if isinstance(exc, FuenteConsultaError):
        base = exc.mensaje
        if "acción:" in base.lower() or "reintent" in base.lower():
            return base
        return f"{base} Acción: reintentar la consulta completa."

    texto = str(exc).strip() or exc.__class__.__name__
    nombre = exc.__class__.__name__
    bajo = f"{nombre} {texto}".lower()

    if "timeout" in bajo:
        return (
            f"{fuente_norm}: tiempo de espera agotado (posible red lenta o portal "
            "saturado). Acción: verifica la conexión y reintenta la consulta."
        )
    if any(
        t in bajo
        for t in ("connection", "network", "errno", "conexión", "conexion", "offline")
    ):
        return (
            f"{fuente_norm}: fallo de red o conexión. "
            "Acción: verifica internet/VPN y reintenta la consulta."
        )
    if "no se encontró" in bajo or "not found" in bajo or "selector" in bajo:
        return (
            f"{fuente_norm}: no se encontró un elemento esperado en el portal "
            f"(posible cambio de página). Detalle: {texto}. "
            "Acción: reintenta; si persiste, reporta a soporte."
        )
    if "captcha" in bajo:
        return (
            f"{fuente_norm}: problema con el CAPTCHA. "
            f"Detalle: {texto}. Acción: reintenta e ingresa el CAPTCHA con cuidado."
        )
    return (
        f"{fuente_norm}: {texto}. "
        "Acción: reintenta la consulta; si el error se repite, reporta a soporte."
    )
