"""
Modelos de dominio RUNT (contrato versionado).

``schema_version`` documenta la forma de ``secciones`` para evolucionar
parsers/persistencia sin congelar un dict opaco (ticket C-01 / RF-16).

Estructura de ``secciones`` (schema_version=\"1\"):
    - Claves: títulos normalizados de paneles RUNT (str), p. ej.
      ``DATOS PERSONALES``, ``LICENCIAS``, ``MULTAS E INFRACCIONES``.
    - Valores (uno de):
        * ``None`` — panel sin contenido usable
        * ``list[dict[str, Any]]`` — filas de tabla / cards
        * ``dict[str, Any]`` — pares label/valor
        * ``str`` — fallback de texto plano

``tiene_multas_inferidas`` es un campo **derivado/heurístico** a partir de
secciones de multas/infracciones. No indica elegibilidad ni permiso de
trámite; solo resume lo que el portal expuso en esa consulta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION_RUNT = "1"

_CLAVES_MULTAS_INFRACCIONES: List[str] = [
    "MULTAS E INFRACCIONES",
    "MULTAS",
    "INFRACCIONES",
]


def inferir_multas_desde_secciones(secciones: Dict[str, Any]) -> bool:
    """
    Heurística: ¿hay contenido no vacío en secciones de multas/infracciones?

    No es un hecho normativo ni una decisión de trámite.
    """
    multas_data: Any = None
    for clave in _CLAVES_MULTAS_INFRACCIONES:
        if clave in secciones:
            multas_data = secciones.get(clave)
            break

    if multas_data is None:
        return False
    if isinstance(multas_data, list):
        return len(multas_data) > 0
    if isinstance(multas_data, dict):
        return len(multas_data) > 0
    return bool(str(multas_data).strip())


@dataclass
class ConsultaRuntParams:
    tipo_documento: str
    numero_documento: str


@dataclass
class ResultadoRunt:
    """Resultado estructurado de una consulta ciudadana a RUNT."""

    schema_version: str = SCHEMA_VERSION_RUNT

    # Campos tipados (hechos reportados / extractos del parser)
    nombre: Optional[str] = None
    estado_licencia: Optional[str] = None  # "estado_conductor" del portal
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    estado_persona: Optional[str] = None
    numero_inscripcion: Optional[str] = None
    fecha_inscripcion: Optional[str] = None

    # Derivado/heurístico — NO es elegibilidad de trámite
    tiene_multas_inferidas: Optional[bool] = None

    # Payload versionado por secciones (ver docstring del módulo)
    secciones: Dict[str, Any] = field(default_factory=dict)

    # Evidencia / estados operativos
    raw_html: Optional[str] = None
    sin_registro: bool = False
    error: Optional[str] = None
