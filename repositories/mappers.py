"""Mapeo entre modelos de dominio (C-01) y filas del esquema D-01."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional
from uuid import UUID

from models.consulta_models import EstadoFuente, ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import (
    AcuerdoPago,
    ComparendoMulta,
    ResultadoSimit,
    ResumenSimit,
    TotalSeccion,
)

SCHEMA_VERSION_CONSULTA = "1"

_ESTADOS_DB_FUENTE = frozenset({"ok", "parcial", "error", "omitido"})
_ESTADOS_DB_CONSULTA = frozenset(
    {"en_progreso", "ok", "parcial", "error", "omitido"}
)


def estado_fuente_a_db(estado: EstadoFuente) -> str:
    """
    Compacta estados de UI a check constraint de ``resultados_*``.

    ``sin_registro`` / ``sin_pendientes`` → ``ok`` (el detalle va en columnas/JSON).
    """
    if estado in ("ok", "sin_registro", "sin_pendientes"):
        return "ok"
    if estado in _ESTADOS_DB_FUENTE:
        return estado
    return "parcial"


def estado_consulta_a_db(resultado: ResultadoConsulta) -> str:
    if resultado.estado_global is None:
        return "en_progreso"
    if resultado.estado_global in _ESTADOS_DB_CONSULTA:
        return resultado.estado_global
    return "en_progreso"


def duracion_ms(
    inicio: Optional[datetime], fin: Optional[datetime]
) -> Optional[int]:
    if inicio is None or fin is None:
        return None
    delta = fin - inicio
    ms = int(delta.total_seconds() * 1000)
    return ms if ms >= 0 else None


def to_jsonable(obj: Any) -> Any:
    """Convierte dataclasses / colecciones a estructuras JSON-serializables."""
    if obj is None:
        return None
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    return obj


def debe_persistir_runt(resultado: ResultadoConsulta) -> bool:
    if resultado.modo == "PLACA":
        return False
    return resultado.resultado_runt is not None or bool(resultado.error_runt)


def debe_persistir_simit(resultado: ResultadoConsulta) -> bool:
    return resultado.resultado_simit is not None or bool(resultado.error_simit)


def fila_runt_desde_resultado(
    resultado: ResultadoConsulta,
) -> Dict[str, Any]:
    runt = resultado.resultado_runt or ResultadoRunt()
    error = resultado.error_runt or runt.error
    return {
        "schema_version": runt.schema_version,
        "estado": estado_fuente_a_db(resultado.estado_fuente_runt()),
        "sin_registro": bool(runt.sin_registro),
        "nombre": runt.nombre,
        "estado_licencia": runt.estado_licencia,
        "tipo_documento": runt.tipo_documento or resultado.tipo_documento,
        "numero_documento": runt.numero_documento or (
            resultado.identificador if resultado.modo == "DOCUMENTO" else None
        ),
        "estado_persona": runt.estado_persona,
        "numero_inscripcion": runt.numero_inscripcion,
        "fecha_inscripcion": runt.fecha_inscripcion,
        "tiene_multas_inferidas": runt.tiene_multas_inferidas,
        "secciones": to_jsonable(runt.secciones) or {},
        "raw_html": runt.raw_html,
        "error_mensaje": error,
        "duracion_ms": None,
    }


def fila_simit_desde_resultado(
    resultado: ResultadoConsulta,
) -> Dict[str, Any]:
    simit = resultado.resultado_simit or ResultadoSimit()
    error = resultado.error_simit or simit.error
    return {
        "schema_version": simit.schema_version,
        "estado": estado_fuente_a_db(resultado.estado_fuente_simit()),
        "sin_registro": bool(simit.sin_registro),
        "resumen": to_jsonable(simit.resumen),
        "comparendos_multas": to_jsonable(simit.comparendos_multas) or [],
        "acuerdos_pago": to_jsonable(simit.acuerdos_pago) or [],
        "total_comparendos_multas": to_jsonable(simit.total_comparendos_multas),
        "total_acuerdos_pago": to_jsonable(simit.total_acuerdos_pago),
        "datos_raw": to_jsonable(simit.datos_raw) or {},
        "raw_html": simit.raw_html,
        "error_mensaje": error,
        "duracion_ms": None,
    }


def _dict_or_none(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return None


def _list_of_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def resultado_runt_desde_fila(row: Mapping[str, Any]) -> ResultadoRunt:
    return ResultadoRunt(
        schema_version=str(row.get("schema_version") or "1"),
        nombre=row.get("nombre"),
        estado_licencia=row.get("estado_licencia"),
        tipo_documento=row.get("tipo_documento"),
        numero_documento=row.get("numero_documento"),
        estado_persona=row.get("estado_persona"),
        numero_inscripcion=row.get("numero_inscripcion"),
        fecha_inscripcion=row.get("fecha_inscripcion"),
        tiene_multas_inferidas=row.get("tiene_multas_inferidas"),
        secciones=_dict_or_none(row.get("secciones")) or {},
        raw_html=row.get("raw_html"),
        sin_registro=bool(row.get("sin_registro")),
        error=row.get("error_mensaje"),
    )


def _resumen_desde_json(data: Optional[Dict[str, Any]]) -> Optional[ResumenSimit]:
    if not data:
        return None
    return ResumenSimit(
        identificador=str(data.get("identificador") or ""),
        modo=str(data.get("modo") or ""),
        comparendos=int(data.get("comparendos") or 0),
        multas=int(data.get("multas") or 0),
        acuerdos_pago=int(data.get("acuerdos_pago") or 0),
        cedula=data.get("cedula"),
        total=data.get("total"),
        mensaje_estado=data.get("mensaje_estado"),
        sin_pendientes=bool(data.get("sin_pendientes")),
    )


def _total_desde_json(data: Optional[Dict[str, Any]]) -> Optional[TotalSeccion]:
    if not data:
        return None
    return TotalSeccion(
        cantidad=int(data.get("cantidad") or 0),
        valor=data.get("valor"),
    )


def resultado_simit_desde_fila(row: Mapping[str, Any]) -> ResultadoSimit:
    comparendos = [
        ComparendoMulta(**{k: d.get(k) for k in ComparendoMulta.__dataclass_fields__})
        for d in _list_of_dicts(row.get("comparendos_multas"))
    ]
    acuerdos = [
        AcuerdoPago(**{k: d.get(k) for k in AcuerdoPago.__dataclass_fields__})
        for d in _list_of_dicts(row.get("acuerdos_pago"))
    ]
    return ResultadoSimit(
        schema_version=str(row.get("schema_version") or "1"),
        resumen=_resumen_desde_json(_dict_or_none(row.get("resumen"))),
        comparendos_multas=comparendos,
        acuerdos_pago=acuerdos,
        total_comparendos_multas=_total_desde_json(
            _dict_or_none(row.get("total_comparendos_multas"))
        ),
        total_acuerdos_pago=_total_desde_json(
            _dict_or_none(row.get("total_acuerdos_pago"))
        ),
        raw_html=row.get("raw_html"),
        sin_registro=bool(row.get("sin_registro")),
        error=row.get("error_mensaje"),
        datos_raw=_dict_or_none(row.get("datos_raw")) or {},
    )


def as_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
