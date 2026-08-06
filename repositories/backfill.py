"""
Orquestación de backfill F-06 (reutilizable por script y tests).

Lee snapshots capa A y aplica ``normalizar_maestros_y_hechos`` (F-02).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from repositories.backfill_helpers import (
    describir_plan_backfill,
    resultado_consulta_desde_registro,
    tiene_snapshot_util,
)
from repositories.consulta_repository import ConsultaRepository
from repositories.exceptions import PersistenciaError
from utils.logging_setup import get_logger


@dataclass
class ResumenBackfill:
    candidatas: int = 0
    procesadas: int = 0
    omitidas: int = 0
    errores: int = 0
    dry_run: bool = False
    detalle_errores: List[str] = field(default_factory=list)


def ejecutar_backfill(
    repo: ConsultaRepository,
    *,
    dry_run: bool = False,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limit: Optional[int] = None,
    solo_sin_fk: bool = False,
    log=None,
) -> ResumenBackfill:
    """Errores por fila no abortan el lote; resumen al final."""
    logger = log or get_logger(__name__)
    resumen = ResumenBackfill(dry_run=dry_run)

    ids = repo.listar_consultas_para_backfill(
        desde=desde,
        hasta=hasta,
        limit=limit,
        solo_sin_fk=solo_sin_fk,
    )
    resumen.candidatas = len(ids)
    logger.info(
        "Backfill F-06: %s candidata(s) dry_run=%s solo_sin_fk=%s",
        resumen.candidatas,
        dry_run,
        solo_sin_fk,
    )

    for consulta_id in ids:
        try:
            reg = repo.obtener_por_id(consulta_id, con_resultados=True)
            if reg is None:
                resumen.omitidas += 1
                logger.warning("Consulta %s no encontrada; omitida", consulta_id)
                continue

            desc = describir_plan_backfill(reg)
            cid = reg.correlation_id or "-"
            if desc.omitida:
                resumen.omitidas += 1
                logger.info(
                    "Omitida consulta_id=%s cid=%s: %s",
                    consulta_id,
                    cid,
                    desc.motivo_omitida,
                )
                continue

            if dry_run:
                resumen.procesadas += 1
                logger.info(
                    "[dry-run] consulta_id=%s cid=%s modo=%s id=%s → %s",
                    consulta_id,
                    cid,
                    reg.modo,
                    reg.identificador,
                    "; ".join(desc.lineas),
                )
                continue

            if not tiene_snapshot_util(reg):
                resumen.omitidas += 1
                continue

            resultado = resultado_consulta_desde_registro(reg)
            ids_fk = repo.normalizar_maestros_y_hechos(consulta_id, resultado)
            resumen.procesadas += 1
            logger.info(
                "OK consulta_id=%s cid=%s persona_id=%s vehiculo_id=%s (%s)",
                consulta_id,
                cid,
                ids_fk.get("persona_id"),
                ids_fk.get("vehiculo_id"),
                "; ".join(desc.lineas),
            )
            try:
                repo.agregar_evento(
                    consulta_id,
                    "Backfill maestros/hechos desde snapshot",
                    fuente="SISTEMA",
                    nivel="info",
                    codigo="BACKFILL_NORMALIZADO",
                    detalle={
                        "correlation_id": reg.correlation_id,
                        "persona_id": str(ids_fk.get("persona_id") or ""),
                        "vehiculo_id": str(ids_fk.get("vehiculo_id") or ""),
                    },
                )
            except PersistenciaError:
                logger.warning(
                    "Normalización OK pero falló evento BACKFILL consulta_id=%s",
                    consulta_id,
                )
        except PersistenciaError as exc:
            resumen.errores += 1
            msg = f"consulta_id={consulta_id}: {exc.mensaje}"
            resumen.detalle_errores.append(msg)
            logger.error("Error backfill %s", msg, exc_info=True)
        except Exception as exc:
            resumen.errores += 1
            msg = f"consulta_id={consulta_id}: {exc}"
            resumen.detalle_errores.append(msg)
            logger.error("Error inesperado backfill %s", msg, exc_info=True)

    logger.info(
        "Resumen backfill: candidatas=%s procesadas=%s omitidas=%s errores=%s dry_run=%s",
        resumen.candidatas,
        resumen.procesadas,
        resumen.omitidas,
        resumen.errores,
        dry_run,
    )
    return resumen
