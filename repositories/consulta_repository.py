"""
Repositorio de consultas y resultados por fuente (esquema D-01).

Solo persiste hechos/metadatos — sin lógica de elegibilidad.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit
from repositories.connection import Database, get_database
from repositories.exceptions import PersistenciaError
from repositories.mappers import (
    SCHEMA_VERSION_CONSULTA,
    as_uuid,
    debe_persistir_runt,
    debe_persistir_simit,
    duracion_ms,
    estado_consulta_a_db,
    fila_runt_desde_resultado,
    fila_simit_desde_resultado,
    resultado_runt_desde_fila,
    resultado_simit_desde_fila,
    to_jsonable,
)
from utils.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class ConsultaRegistro:
    """Fila de ``consultas`` más resultados opcionales por fuente."""

    id: UUID
    correlation_id: Optional[str]
    modo: str
    identificador: str
    tipo_documento: Optional[str]
    estado: str
    schema_version: str
    iniciado_en: Optional[datetime]
    finalizado_en: Optional[datetime]
    error_runt: Optional[str]
    error_simit: Optional[str]
    resultado_runt: Optional[ResultadoRunt] = None
    resultado_simit: Optional[ResultadoSimit] = None


@dataclass
class EventoConsulta:
    id: UUID
    consulta_id: UUID
    fuente: Optional[str]
    nivel: str
    codigo: Optional[str]
    mensaje: str
    detalle: Dict[str, Any]
    created_at: datetime


class ConsultaRepository:
    """Alta/lectura de consultas, resultados RUNT/SIMIT y eventos."""

    def __init__(self, database: Optional[Database] = None) -> None:
        self._db = database or get_database()

    def persistir_resultado_consulta(
        self,
        resultado: ResultadoConsulta,
        *,
        operador: Optional[str] = None,
        estacion: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> UUID:
        """
        Inserta cabecera + resultados por fuente en una transacción.

        Pensado para D-03 (post-consulta). No calcula elegibilidad.
        """
        try:
            with self._db.connection() as conn:
                consulta_id = self._insert_consulta(
                    conn,
                    resultado,
                    operador=operador,
                    estacion=estacion,
                    app_version=app_version,
                )
                if debe_persistir_runt(resultado):
                    self._upsert_runt(
                        conn, consulta_id, fila_runt_desde_resultado(resultado)
                    )
                if debe_persistir_simit(resultado):
                    self._upsert_simit(
                        conn, consulta_id, fila_simit_desde_resultado(resultado)
                    )
                logger.info(
                    "Consulta persistida id=%s modo=%s estado=%s",
                    consulta_id,
                    resultado.modo,
                    estado_consulta_a_db(resultado),
                )
                return consulta_id
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error("Error SQL al persistir consulta: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudo persistir la consulta: {exc}",
                causa=exc,
            ) from exc

    def crear_consulta(
        self,
        *,
        modo: str,
        identificador: str,
        tipo_documento: Optional[str] = None,
        correlation_id: Optional[str] = None,
        estado: str = "en_progreso",
        operador: Optional[str] = None,
        estacion: Optional[str] = None,
        app_version: Optional[str] = None,
        iniciado_en: Optional[datetime] = None,
    ) -> UUID:
        """Alta mínima de cabecera (estado inicial típico: en_progreso)."""
        resultado = ResultadoConsulta(
            modo=modo,
            identificador=identificador,
            tipo_documento=tipo_documento,
            correlation_id=correlation_id,
            iniciado_en=iniciado_en,
        )
        try:
            with self._db.connection() as conn:
                return self._insert_consulta(
                    conn,
                    resultado,
                    operador=operador,
                    estacion=estacion,
                    app_version=app_version,
                    estado_override=estado,
                )
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error("Error SQL al crear consulta: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudo crear la consulta: {exc}",
                causa=exc,
            ) from exc

    def actualizar_estado_consulta(
        self,
        consulta_id: UUID,
        *,
        estado: str,
        error_runt: Optional[str] = None,
        error_simit: Optional[str] = None,
        finalizado_en: Optional[datetime] = None,
        duracion_ms_val: Optional[int] = None,
    ) -> None:
        try:
            with self._db.connection() as conn:
                conn.execute(
                    """
                    update public.consultas
                       set estado = %(estado)s,
                           error_runt = coalesce(%(error_runt)s, error_runt),
                           error_simit = coalesce(%(error_simit)s, error_simit),
                           finalizado_en = coalesce(%(finalizado_en)s, finalizado_en),
                           duracion_ms = coalesce(%(duracion_ms)s, duracion_ms)
                     where id = %(id)s
                    """,
                    {
                        "id": consulta_id,
                        "estado": estado,
                        "error_runt": error_runt,
                        "error_simit": error_simit,
                        "finalizado_en": finalizado_en,
                        "duracion_ms": duracion_ms_val,
                    },
                )
        except psycopg.Error as exc:
            logger.error(
                "Error SQL al actualizar consulta %s: %s",
                consulta_id,
                exc,
                exc_info=True,
            )
            raise PersistenciaError(
                f"No se pudo actualizar la consulta {consulta_id}: {exc}",
                causa=exc,
            ) from exc

    def guardar_resultado_runt(
        self, consulta_id: UUID, resultado: ResultadoConsulta
    ) -> UUID:
        if not debe_persistir_runt(resultado):
            raise PersistenciaError(
                "No hay hechos RUNT para persistir (modo PLACA o sin datos/error)."
            )
        try:
            with self._db.connection() as conn:
                return self._upsert_runt(
                    conn, consulta_id, fila_runt_desde_resultado(resultado)
                )
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error("Error SQL al guardar RUNT: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudo guardar resultado RUNT: {exc}",
                causa=exc,
            ) from exc

    def guardar_resultado_simit(
        self, consulta_id: UUID, resultado: ResultadoConsulta
    ) -> UUID:
        if not debe_persistir_simit(resultado):
            raise PersistenciaError("No hay hechos SIMIT para persistir.")
        try:
            with self._db.connection() as conn:
                return self._upsert_simit(
                    conn, consulta_id, fila_simit_desde_resultado(resultado)
                )
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error("Error SQL al guardar SIMIT: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudo guardar resultado SIMIT: {exc}",
                causa=exc,
            ) from exc

    def agregar_evento(
        self,
        consulta_id: UUID,
        mensaje: str,
        *,
        fuente: Optional[str] = None,
        nivel: str = "info",
        codigo: Optional[str] = None,
        detalle: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        try:
            with self._db.connection() as conn:
                row = conn.execute(
                    """
                    insert into public.eventos_consulta (
                        consulta_id, fuente, nivel, codigo, mensaje, detalle
                    ) values (
                        %(consulta_id)s, %(fuente)s, %(nivel)s, %(codigo)s,
                        %(mensaje)s, %(detalle)s
                    )
                    returning id
                    """,
                    {
                        "consulta_id": consulta_id,
                        "fuente": fuente,
                        "nivel": nivel,
                        "codigo": codigo,
                        "mensaje": mensaje,
                        "detalle": Jsonb(to_jsonable(detalle) or {}),
                    },
                ).fetchone()
                assert row is not None
                return as_uuid(row["id"])
        except psycopg.Error as exc:
            logger.error("Error SQL al agregar evento: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudo agregar evento: {exc}",
                causa=exc,
            ) from exc

    def obtener_por_id(
        self, consulta_id: UUID, *, con_resultados: bool = True
    ) -> Optional[ConsultaRegistro]:
        try:
            with self._db.connection() as conn:
                row = conn.execute(
                    """
                    select id, correlation_id, modo, identificador, tipo_documento,
                           estado, schema_version, iniciado_en, finalizado_en,
                           error_runt, error_simit
                      from public.consultas
                     where id = %(id)s
                    """,
                    {"id": consulta_id},
                ).fetchone()
                if row is None:
                    return None
                registro = self._consulta_desde_fila(row)
                if con_resultados:
                    runt = conn.execute(
                        "select * from public.resultados_runt where consulta_id = %(id)s",
                        {"id": consulta_id},
                    ).fetchone()
                    if runt:
                        registro.resultado_runt = resultado_runt_desde_fila(runt)
                    simit = conn.execute(
                        "select * from public.resultados_simit where consulta_id = %(id)s",
                        {"id": consulta_id},
                    ).fetchone()
                    if simit:
                        registro.resultado_simit = resultado_simit_desde_fila(simit)
                return registro
        except psycopg.Error as exc:
            logger.error(
                "Error SQL al leer consulta %s: %s", consulta_id, exc, exc_info=True
            )
            raise PersistenciaError(
                f"No se pudo leer la consulta {consulta_id}: {exc}",
                causa=exc,
            ) from exc

    def listar_eventos(self, consulta_id: UUID) -> List[EventoConsulta]:
        try:
            with self._db.connection() as conn:
                rows = conn.execute(
                    """
                    select id, consulta_id, fuente, nivel, codigo, mensaje,
                           detalle, created_at
                      from public.eventos_consulta
                     where consulta_id = %(id)s
                     order by created_at asc
                    """,
                    {"id": consulta_id},
                ).fetchall()
                return [
                    EventoConsulta(
                        id=as_uuid(r["id"]),
                        consulta_id=as_uuid(r["consulta_id"]),
                        fuente=r.get("fuente"),
                        nivel=str(r["nivel"]),
                        codigo=r.get("codigo"),
                        mensaje=str(r["mensaje"]),
                        detalle=dict(r.get("detalle") or {}),
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]
        except psycopg.Error as exc:
            logger.error("Error SQL al listar eventos: %s", exc, exc_info=True)
            raise PersistenciaError(
                f"No se pudieron listar eventos: {exc}",
                causa=exc,
            ) from exc

    # ------------------------------------------------------------------
    # SQL helpers
    # ------------------------------------------------------------------

    def _insert_consulta(
        self,
        conn: psycopg.Connection,
        resultado: ResultadoConsulta,
        *,
        operador: Optional[str],
        estacion: Optional[str],
        app_version: Optional[str],
        estado_override: Optional[str] = None,
    ) -> UUID:
        estado = estado_override or estado_consulta_a_db(resultado)
        ms = duracion_ms(resultado.iniciado_en, resultado.finalizado_en)
        row = conn.execute(
            """
            insert into public.consultas (
                correlation_id, modo, identificador, tipo_documento, estado,
                operador, estacion, app_version, schema_version,
                iniciado_en, finalizado_en, duracion_ms,
                error_runt, error_simit
            ) values (
                %(correlation_id)s, %(modo)s, %(identificador)s, %(tipo_documento)s,
                %(estado)s, %(operador)s, %(estacion)s, %(app_version)s,
                %(schema_version)s, %(iniciado_en)s, %(finalizado_en)s, %(duracion_ms)s,
                %(error_runt)s, %(error_simit)s
            )
            returning id
            """,
            {
                "correlation_id": resultado.correlation_id,
                "modo": resultado.modo,
                "identificador": resultado.identificador,
                "tipo_documento": resultado.tipo_documento,
                "estado": estado,
                "operador": operador,
                "estacion": estacion,
                "app_version": app_version,
                "schema_version": SCHEMA_VERSION_CONSULTA,
                "iniciado_en": resultado.iniciado_en,
                "finalizado_en": resultado.finalizado_en,
                "duracion_ms": ms,
                "error_runt": resultado.error_runt,
                "error_simit": resultado.error_simit,
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_runt(
        self,
        conn: psycopg.Connection,
        consulta_id: UUID,
        fila: Dict[str, Any],
    ) -> UUID:
        row = conn.execute(
            """
            insert into public.resultados_runt (
                consulta_id, schema_version, estado, sin_registro,
                nombre, estado_licencia, tipo_documento, numero_documento,
                estado_persona, numero_inscripcion, fecha_inscripcion,
                tiene_multas_inferidas, secciones, raw_html, error_mensaje,
                duracion_ms
            ) values (
                %(consulta_id)s, %(schema_version)s, %(estado)s, %(sin_registro)s,
                %(nombre)s, %(estado_licencia)s, %(tipo_documento)s, %(numero_documento)s,
                %(estado_persona)s, %(numero_inscripcion)s, %(fecha_inscripcion)s,
                %(tiene_multas_inferidas)s, %(secciones)s, %(raw_html)s, %(error_mensaje)s,
                %(duracion_ms)s
            )
            on conflict (consulta_id) do update set
                schema_version = excluded.schema_version,
                estado = excluded.estado,
                sin_registro = excluded.sin_registro,
                nombre = excluded.nombre,
                estado_licencia = excluded.estado_licencia,
                tipo_documento = excluded.tipo_documento,
                numero_documento = excluded.numero_documento,
                estado_persona = excluded.estado_persona,
                numero_inscripcion = excluded.numero_inscripcion,
                fecha_inscripcion = excluded.fecha_inscripcion,
                tiene_multas_inferidas = excluded.tiene_multas_inferidas,
                secciones = excluded.secciones,
                raw_html = excluded.raw_html,
                error_mensaje = excluded.error_mensaje,
                duracion_ms = excluded.duracion_ms
            returning id
            """,
            {
                "consulta_id": consulta_id,
                "schema_version": fila["schema_version"],
                "estado": fila["estado"],
                "sin_registro": fila["sin_registro"],
                "nombre": fila["nombre"],
                "estado_licencia": fila["estado_licencia"],
                "tipo_documento": fila["tipo_documento"],
                "numero_documento": fila["numero_documento"],
                "estado_persona": fila["estado_persona"],
                "numero_inscripcion": fila["numero_inscripcion"],
                "fecha_inscripcion": fila["fecha_inscripcion"],
                "tiene_multas_inferidas": fila["tiene_multas_inferidas"],
                "secciones": Jsonb(fila["secciones"]),
                "raw_html": fila["raw_html"],
                "error_mensaje": fila["error_mensaje"],
                "duracion_ms": fila["duracion_ms"],
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_simit(
        self,
        conn: psycopg.Connection,
        consulta_id: UUID,
        fila: Dict[str, Any],
    ) -> UUID:
        row = conn.execute(
            """
            insert into public.resultados_simit (
                consulta_id, schema_version, estado, sin_registro,
                resumen, comparendos_multas, acuerdos_pago,
                total_comparendos_multas, total_acuerdos_pago, datos_raw,
                raw_html, error_mensaje, duracion_ms
            ) values (
                %(consulta_id)s, %(schema_version)s, %(estado)s, %(sin_registro)s,
                %(resumen)s, %(comparendos_multas)s, %(acuerdos_pago)s,
                %(total_comparendos_multas)s, %(total_acuerdos_pago)s, %(datos_raw)s,
                %(raw_html)s, %(error_mensaje)s, %(duracion_ms)s
            )
            on conflict (consulta_id) do update set
                schema_version = excluded.schema_version,
                estado = excluded.estado,
                sin_registro = excluded.sin_registro,
                resumen = excluded.resumen,
                comparendos_multas = excluded.comparendos_multas,
                acuerdos_pago = excluded.acuerdos_pago,
                total_comparendos_multas = excluded.total_comparendos_multas,
                total_acuerdos_pago = excluded.total_acuerdos_pago,
                datos_raw = excluded.datos_raw,
                raw_html = excluded.raw_html,
                error_mensaje = excluded.error_mensaje,
                duracion_ms = excluded.duracion_ms
            returning id
            """,
            {
                "consulta_id": consulta_id,
                "schema_version": fila["schema_version"],
                "estado": fila["estado"],
                "sin_registro": fila["sin_registro"],
                "resumen": Jsonb(fila["resumen"]) if fila["resumen"] is not None else None,
                "comparendos_multas": Jsonb(fila["comparendos_multas"]),
                "acuerdos_pago": Jsonb(fila["acuerdos_pago"]),
                "total_comparendos_multas": (
                    Jsonb(fila["total_comparendos_multas"])
                    if fila["total_comparendos_multas"] is not None
                    else None
                ),
                "total_acuerdos_pago": (
                    Jsonb(fila["total_acuerdos_pago"])
                    if fila["total_acuerdos_pago"] is not None
                    else None
                ),
                "datos_raw": Jsonb(fila["datos_raw"]),
                "raw_html": fila["raw_html"],
                "error_mensaje": fila["error_mensaje"],
                "duracion_ms": fila["duracion_ms"],
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    @staticmethod
    def _consulta_desde_fila(row: Dict[str, Any]) -> ConsultaRegistro:
        return ConsultaRegistro(
            id=as_uuid(row["id"]),
            correlation_id=row.get("correlation_id"),
            modo=str(row["modo"]),
            identificador=str(row["identificador"]),
            tipo_documento=row.get("tipo_documento"),
            estado=str(row["estado"]),
            schema_version=str(row.get("schema_version") or SCHEMA_VERSION_CONSULTA),
            iniciado_en=row.get("iniciado_en"),
            finalizado_en=row.get("finalizado_en"),
            error_runt=row.get("error_runt"),
            error_simit=row.get("error_simit"),
        )
