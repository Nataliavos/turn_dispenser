from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class ConsultaRuntParams:
    tipo_documento: str
    numero_documento: str

@dataclass
class ResultadoRunt:
     # Resumen
    nombre: Optional[str] = None
    estado_licencia: Optional[str] = None  # aquí usaremos "estado_conductor" del parser
    tiene_multas: Optional[bool] = None

    # Datos completos parseados por secciones
    secciones: Dict[str, Any] = field(default_factory=dict)

    # Debug / trazabilidad
    raw_html: Optional[str] = None
    sin_registro: bool = False