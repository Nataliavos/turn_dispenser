"""
Modelos de orquestación de consulta (metadatos + resultados por fuente).

``ResultadoConsulta`` es el contrato estable previo a persistencia (C-01 / RF-13):
incluye correlación, timestamps y un estado global derivado de las fuentes,
sin reglas de elegibilidad de trámites.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit

EstadoFuente = Literal[
    "ok",
    "error",
    "sin_registro",
    "sin_pendientes",
    "omitido",
]
EstadoConsultaGlobal = Literal["ok", "parcial", "error", "omitido"]

_ESTADOS_FUENTE_OK = frozenset({"ok", "sin_registro", "sin_pendientes"})


@dataclass
class ConsultaParams:
    modo: str  # "DOCUMENTO" | "PLACA"
    identificador: str
    tipo_documento: Optional[str] = None  # CC, CE, etc. — solo para modo DOCUMENTO


@dataclass
class ResultadoConsulta:
    """
    Resultado agregado de una consulta RUNT/SIMIT.

    Metadatos (correlation_id, timestamps, estado_global) soportan trazabilidad
    y persistencia futura; no implican decisión de trámite.
    """

    modo: str
    identificador: str
    tipo_documento: Optional[str] = None
    correlation_id: Optional[str] = None
    iniciado_en: Optional[datetime] = None
    finalizado_en: Optional[datetime] = None
    estado_global: Optional[EstadoConsultaGlobal] = None
    resultado_runt: Optional[ResultadoRunt] = None
    resultado_simit: Optional[ResultadoSimit] = None
    error_runt: Optional[str] = None
    error_simit: Optional[str] = None

    def estado_fuente_runt(self) -> EstadoFuente:
        """Resumen corto para UI: ok | error | sin_registro | omitido."""
        if self.modo == "PLACA":
            return "omitido"
        if self.error_runt:
            return "error"
        if self.resultado_runt is None:
            return "omitido"
        if self.resultado_runt.error:
            return "error"
        if self.resultado_runt.sin_registro:
            return "sin_registro"
        return "ok"

    def estado_fuente_simit(self) -> EstadoFuente:
        """Resumen corto para UI: ok | error | sin_registro | sin_pendientes | omitido."""
        if self.error_simit:
            return "error"
        if self.resultado_simit is None:
            return "omitido"
        if self.resultado_simit.error:
            return "error"
        if self.resultado_simit.sin_registro:
            return "sin_registro"
        resumen = self.resultado_simit.resumen
        if resumen and resumen.sin_pendientes and not self.resultado_simit.comparendos_multas:
            return "sin_pendientes"
        return "ok"

    def calcular_estado_global(self) -> EstadoConsultaGlobal:
        """
        Estado agregado de la consulta.

        - ``ok``: todas las fuentes consultadas respondieron sin error operativo
          (incluye sin_registro / sin_pendientes).
        - ``parcial``: al menos una fuente OK y al menos una con error.
        - ``error``: todas las fuentes consultadas fallaron.
        - ``omitido``: ninguna fuente consultada.
        """
        estados: list[EstadoFuente] = []
        estado_runt = self.estado_fuente_runt()
        estado_simit = self.estado_fuente_simit()
        if estado_runt != "omitido":
            estados.append(estado_runt)
        if estado_simit != "omitido":
            estados.append(estado_simit)

        if not estados:
            return "omitido"

        n_error = sum(1 for e in estados if e == "error")
        if n_error == len(estados):
            return "error"
        if n_error > 0:
            return "parcial"
        if all(e in _ESTADOS_FUENTE_OK for e in estados):
            return "ok"
        return "parcial"

    def marcar_inicio(
        self,
        *,
        correlation_id: Optional[str] = None,
        tipo_documento: Optional[str] = None,
        momento: Optional[datetime] = None,
    ) -> None:
        """Rellena metadatos de inicio de consulta."""
        if correlation_id is not None:
            self.correlation_id = correlation_id
        if tipo_documento is not None:
            self.tipo_documento = tipo_documento
        self.iniciado_en = momento or datetime.now(timezone.utc)

    def finalizar(self, momento: Optional[datetime] = None) -> None:
        """Cierra timestamps y congela ``estado_global``."""
        self.finalizado_en = momento or datetime.now(timezone.utc)
        self.estado_global = self.calcular_estado_global()
