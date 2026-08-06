"""
Helpers de backfill F-06: reconstruir ``ResultadoConsulta`` desde snapshots
y describir el plan de normalización sin escribir BD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID

from models.consulta_models import ResultadoConsulta
from repositories.consulta_repository import ConsultaRegistro
from repositories.normalizacion_mappers import (
    PlanNormalizacion,
    plan_normalizacion_desde_resultado,
)

_ESTADOS_GLOBAL = frozenset({"ok", "parcial", "error", "omitido"})


def resultado_consulta_desde_registro(reg: ConsultaRegistro) -> ResultadoConsulta:
    """
    Reconstruye el contrato de persistencia a partir de capa A.

    No re-consulta portales. Campos incompletos en JSONB se toleran
    (el plan de normalización degrada sin crash).
    """
    estado = reg.estado if reg.estado in _ESTADOS_GLOBAL else None
    return ResultadoConsulta(
        modo=reg.modo,
        identificador=reg.identificador,
        tipo_documento=reg.tipo_documento,
        correlation_id=reg.correlation_id,
        iniciado_en=reg.iniciado_en,
        finalizado_en=reg.finalizado_en,
        estado_global=estado,  # type: ignore[arg-type]
        resultado_runt=reg.resultado_runt,
        resultado_simit=reg.resultado_simit,
        error_runt=reg.error_runt,
        error_simit=reg.error_simit,
        persistido=True,
        consulta_db_id=reg.id,
    )


def tiene_snapshot_util(reg: ConsultaRegistro) -> bool:
    """True si hay al menos un snapshot RUNT o SIMIT para normalizar."""
    return reg.resultado_runt is not None or reg.resultado_simit is not None


@dataclass
class DescripcionPlanBackfill:
    consulta_id: UUID
    correlation_id: Optional[str]
    modo: str
    identificador: str
    lineas: List[str] = field(default_factory=list)
    omitida: bool = False
    motivo_omitida: Optional[str] = None


def describir_plan_backfill(
    reg: ConsultaRegistro,
    plan: Optional[PlanNormalizacion] = None,
) -> DescripcionPlanBackfill:
    """Resumen legible de lo que ``normalizar_maestros_y_hechos`` haría."""
    desc = DescripcionPlanBackfill(
        consulta_id=reg.id,
        correlation_id=reg.correlation_id,
        modo=reg.modo,
        identificador=reg.identificador,
    )
    if not tiene_snapshot_util(reg):
        desc.omitida = True
        desc.motivo_omitida = "sin resultados_runt ni resultados_simit"
        return desc

    resultado = resultado_consulta_desde_registro(reg)
    plan_n = plan or plan_normalizacion_desde_resultado(resultado)
    lineas: List[str] = []

    if plan_n.persona is not None:
        p = plan_n.persona
        lineas.append(
            f"persona upsert {p.tipo_documento}/{p.numero_documento}"
            + (f" ({p.nombre_completo})" if p.nombre_completo else "")
        )
    for v in plan_n.vehiculos:
        lineas.append(f"vehiculo upsert {v.placa}")
    if plan_n.vinculos:
        lineas.append(f"vinculos persona_vehiculo: {len(plan_n.vinculos)}")
    if plan_n.licencias:
        lineas.append(f"licencias: {len(plan_n.licencias)}")
    if plan_n.infracciones_runt:
        lineas.append(f"infracciones_runt: {len(plan_n.infracciones_runt)}")
    if plan_n.obligaciones_simit:
        lineas.append(f"obligaciones_simit: {len(plan_n.obligaciones_simit)}")
    if plan_n.acuerdos_pago_simit:
        lineas.append(f"acuerdos_pago_simit: {len(plan_n.acuerdos_pago_simit)}")

    if not lineas:
        desc.omitida = True
        desc.motivo_omitida = "plan vacío (sin maestros/hechos derivables)"
        return desc

    desc.lineas = lineas
    return desc
