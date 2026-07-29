from dataclasses import dataclass
from typing import Optional

from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit


@dataclass
class ConsultaParams:
    modo: str  # "DOCUMENTO" | "PLACA"
    identificador: str
    tipo_documento: Optional[str] = None  # CC, CE, etc. — solo para modo DOCUMENTO


@dataclass
class ResultadoConsulta:
    modo: str
    identificador: str
    resultado_runt: Optional[ResultadoRunt] = None
    resultado_simit: Optional[ResultadoSimit] = None
    error_runt: Optional[str] = None
    error_simit: Optional[str] = None

    def estado_fuente_runt(self) -> str:
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

    def estado_fuente_simit(self) -> str:
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
