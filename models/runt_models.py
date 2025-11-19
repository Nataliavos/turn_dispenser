from dataclasses import dataclass
from typing import Optional

@dataclass
class ConsultaRuntParams:
    tipo_documento: str
    numero_documento: str

@dataclass
class ResultadoRunt:
    # Luego llenaremos esto con el scrapeo
    nombre: Optional[str] = None
    estado_licencia: Optional[str] = None
    tiene_multas: Optional[bool] = None
    raw_html: Optional[str] = None