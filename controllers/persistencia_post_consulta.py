"""
Persistencia síncrona post-consulta (D-03 / F-02).

Orden v2: snapshot capa A (obligatorio si habilitado) → normalización B/C
best-effort. No tumba la consulta si falla la BD: anota el error en
``ResultadoConsulta`` y deja los hechos de RUNT/SIMIT disponibles para UI/CLI.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from config.settings import Settings, get_settings
from models.consulta_models import ResultadoConsulta
from repositories import ConsultaRepository, get_database
from repositories.exceptions import PersistenciaError
from utils.logging_setup import get_logger

logger = get_logger(__name__)


def intentar_persistir_resultado(
    resultado: ResultadoConsulta,
    *,
    settings: Optional[Settings] = None,
    repository: Optional[ConsultaRepository] = None,
) -> None:
    """
    Intenta guardar la consulta finalizada.

    Mutates ``resultado``:
    - ``persistencia_omitida`` si el flag está off
    - ``persistido`` / ``consulta_db_id`` si el snapshot OK
    - ``error_persistencia`` solo si falla el snapshot (capa A)

    La normalización de maestros/hechos (B/C) es best-effort: si falla,
    el snapshot permanece y se registra en log/evento con ``cid``.
    """
    cfg = settings or get_settings()

    if not cfg.persistencia_enabled:
        resultado.persistencia_omitida = True
        resultado.persistido = None
        resultado.error_persistencia = None
        logger.info(
            "Persistencia omitida (PERSISTENCIA_ENABLED=false) cid=%s",
            resultado.correlation_id,
        )
        return

    if not cfg.database_url:
        msg = (
            "No se pudo guardar la consulta: DATABASE_URL no está configurada. "
            "Define el DSN en .env (ver docs/persistencia.md)."
        )
        resultado.persistido = False
        resultado.error_persistencia = msg
        logger.error("%s cid=%s", msg, resultado.correlation_id)
        return

    try:
        repo = repository or ConsultaRepository(get_database(cfg))
        consulta_id = repo.persistir_resultado_consulta(
            resultado,
            operador=cfg.operador,
            estacion=cfg.estacion,
            app_version=cfg.app_version,
        )
        try:
            repo.agregar_evento(
                consulta_id,
                "Consulta finalizada y persistida",
                fuente="SISTEMA",
                nivel="info",
                codigo="PERSISTIDO",
                detalle={
                    "estado_global": resultado.estado_global,
                    "correlation_id": resultado.correlation_id,
                },
            )
        except PersistenciaError as exc:
            # La fila principal ya quedó; el evento es best-effort.
            logger.warning(
                "Consulta %s guardada pero falló evento: %s",
                consulta_id,
                exc.mensaje,
            )

        resultado.persistido = True
        resultado.consulta_db_id = consulta_id
        resultado.error_persistencia = None
        logger.info(
            "Persistencia OK consulta_id=%s cid=%s estado=%s",
            consulta_id,
            resultado.correlation_id,
            resultado.estado_global,
        )

        _intentar_normalizacion(repo, consulta_id, resultado)
    except PersistenciaError as exc:
        resultado.persistido = False
        resultado.consulta_db_id = None
        resultado.error_persistencia = (
            "No se pudo guardar en la base de datos. "
            "Los resultados de la consulta siguen disponibles en pantalla. "
            f"Detalle: {exc.mensaje}"
        )
        logger.error(
            "Persistencia fallida cid=%s: %s",
            resultado.correlation_id,
            exc.mensaje,
            exc_info=True,
        )
    except Exception as exc:  # red de seguridad: nunca tumbar la consulta
        resultado.persistido = False
        resultado.consulta_db_id = None
        resultado.error_persistencia = (
            "No se pudo guardar en la base de datos (error inesperado). "
            "Los resultados siguen disponibles en pantalla. "
            f"Detalle: {exc}"
        )
        logger.error(
            "Persistencia inesperada cid=%s: %s",
            resultado.correlation_id,
            exc,
            exc_info=True,
        )


def _intentar_normalizacion(
    repo: ConsultaRepository,
    consulta_id: UUID,
    resultado: ResultadoConsulta,
) -> None:
    """Upsert maestros/hechos tras snapshot; fallos no invalidan capa A."""
    try:
        ids = repo.normalizar_maestros_y_hechos(consulta_id, resultado)
        try:
            repo.agregar_evento(
                consulta_id,
                "Normalización maestros/hechos completada",
                fuente="SISTEMA",
                nivel="info",
                codigo="NORMALIZADO",
                detalle={
                    "persona_id": str(ids.get("persona_id") or ""),
                    "vehiculo_id": str(ids.get("vehiculo_id") or ""),
                    "correlation_id": resultado.correlation_id,
                },
            )
        except PersistenciaError:
            logger.warning(
                "Normalización OK pero falló evento consulta_id=%s cid=%s",
                consulta_id,
                resultado.correlation_id,
            )
    except PersistenciaError as exc:
        logger.error(
            "Normalización B/C fallida consulta_id=%s cid=%s: %s "
            "(snapshot capa A intacto)",
            consulta_id,
            resultado.correlation_id,
            exc.mensaje,
            exc_info=True,
        )
        try:
            repo.agregar_evento(
                consulta_id,
                "Normalización maestros/hechos fallida",
                fuente="SISTEMA",
                nivel="warning",
                codigo="NORMALIZACION_FALLIDA",
                detalle={
                    "error": exc.mensaje,
                    "correlation_id": resultado.correlation_id,
                },
            )
        except PersistenciaError:
            pass
    except Exception as exc:
        logger.error(
            "Normalización B/C inesperada consulta_id=%s cid=%s: %s "
            "(snapshot capa A intacto)",
            consulta_id,
            resultado.correlation_id,
            exc,
            exc_info=True,
        )
