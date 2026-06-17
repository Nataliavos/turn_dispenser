from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConsultaSimitParams:
    identificador: str
    modo: str  # "DOCUMENTO" | "PLACA"


@dataclass
class ResumenSimit:
    identificador: str
    modo: str
    comparendos: int = 0
    multas: int = 0
    acuerdos_pago: int = 0
    cedula: Optional[str] = None
    total: Optional[str] = None
    mensaje_estado: Optional[str] = None
    sin_pendientes: bool = False


@dataclass
class ComparendoMulta:
    numero: Optional[str] = None
    tipo: Optional[str] = None
    fecha_imposicion: Optional[str] = None
    notificacion: Optional[str] = None
    placa: Optional[str] = None
    secretaria: Optional[str] = None
    infraccion: Optional[str] = None
    infraccion_descripcion: Optional[str] = None
    estado: Optional[str] = None
    valor: Optional[str] = None
    valor_a_pagar: Optional[str] = None


@dataclass
class AcuerdoPago:
    numero_acuerdo: Optional[str] = None
    fecha: Optional[str] = None
    secretaria: Optional[str] = None
    valor_acuerdo: Optional[str] = None
    pendiente: Optional[str] = None
    cuota: Optional[str] = None
    valor_a_pagar: Optional[str] = None
    descuento: Optional[str] = None


@dataclass
class TotalSeccion:
    """Total al pie de una tabla: ej. 'Total (1): $ 604.100'."""
    cantidad: int
    valor: Optional[str] = None


@dataclass
class ResultadoSimit:
    resumen: Optional[ResumenSimit] = None
    comparendos_multas: List[ComparendoMulta] = field(default_factory=list)
    acuerdos_pago: List[AcuerdoPago] = field(default_factory=list)
    total_comparendos_multas: Optional[TotalSeccion] = None
    total_acuerdos_pago: Optional[TotalSeccion] = None
    raw_html: Optional[str] = None
    sin_registro: bool = False
    error: Optional[str] = None

    # Datos crudos parseados (debug / extensibilidad)
    datos_raw: Dict[str, Any] = field(default_factory=dict)
