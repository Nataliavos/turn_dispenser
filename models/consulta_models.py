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
