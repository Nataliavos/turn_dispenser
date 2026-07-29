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
    """Traduce una excepción a mensaje orientado al operador (RF-20)."""
    fuente_norm = fuente.strip().upper()
    if isinstance(exc, FuenteConsultaError):
        return exc.mensaje

    texto = str(exc).strip() or exc.__class__.__name__
    nombre = exc.__class__.__name__
    bajo = texto.lower()

    if "timeout" in nombre.lower() or "timeout" in bajo:
        return (
            f"{fuente_norm}: tiempo de espera agotado. "
            "Verifica la conexión e intenta de nuevo."
        )
    if "no se encontró" in bajo or "not found" in bajo:
        return (
            f"{fuente_norm}: no se encontró un elemento esperado en el portal "
            f"(posible cambio de página). Detalle: {texto}"
        )
    if "captcha" in bajo:
        return (
            f"{fuente_norm}: problema con el CAPTCHA. "
            f"Vuelve a intentarlo. Detalle: {texto}"
        )
    return f"{fuente_norm}: {texto}"
