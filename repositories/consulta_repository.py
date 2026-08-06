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
from repositories.normalizacion_mappers import (
    FilaAcuerdoPagoSimit,
    FilaInfraccionRunt,
    FilaLicencia,
    FilaObligacionSimit,
    FilaPersona,
    FilaVehiculo,
    PlanNormalizacion,
    plan_normalizacion_desde_resultado,
)
from utils.logging_setup import get_logger
from utils.placa_validator import normalizar_placa

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

    def normalizar_maestros_y_hechos(
        self,
        consulta_id: UUID,
        resultado: ResultadoConsulta,
        *,
        plan: Optional[PlanNormalizacion] = None,
    ) -> Dict[str, Optional[UUID]]:
        """
        Upsert best-effort de maestros (B) y hechos tipados (C) tras el snapshot.

        Actualiza ``consultas.persona_id`` / ``vehiculo_id`` cuando se resuelven.
        No calcula elegibilidad. Fallos → ``PersistenciaError`` (caller decide).
        """
        plan_norm = plan or plan_normalizacion_desde_resultado(resultado)
        try:
            with self._db.connection() as conn:
                persona_id: Optional[UUID] = None
                vehiculo_ids: Dict[str, UUID] = {}

                if plan_norm.persona is not None:
                    persona_id = self._upsert_persona(
                        conn, plan_norm.persona, consulta_id
                    )

                for veh in plan_norm.vehiculos:
                    vehiculo_ids[veh.placa] = self._upsert_vehiculo(
                        conn, veh, consulta_id
                    )

                # Vehículo principal de la consulta (modo PLACA o primera placa).
                vehiculo_consulta_id: Optional[UUID] = None
                if resultado.modo == "PLACA" and resultado.identificador:
                    placa_consulta = normalizar_placa(resultado.identificador)
                    vehiculo_consulta_id = vehiculo_ids.get(placa_consulta)
                elif len(vehiculo_ids) == 1:
                    vehiculo_consulta_id = next(iter(vehiculo_ids.values()))

                if persona_id is not None:
                    for vinculo in plan_norm.vinculos:
                        vid = vehiculo_ids.get(vinculo.placa)
                        if vid is None:
                            continue
                        self._upsert_persona_vehiculo(
                            conn,
                            persona_id=persona_id,
                            vehiculo_id=vid,
                            fuente=vinculo.fuente,
                            consulta_id=consulta_id,
                        )

                    for lic in plan_norm.licencias:
                        self._upsert_licencia(
                            conn, persona_id, lic, consulta_id
                        )

                    for infr in plan_norm.infracciones_runt:
                        vid = (
                            vehiculo_ids.get(infr.placa)
                            if infr.placa
                            else None
                        )
                        self._upsert_infraccion_runt(
                            conn,
                            persona_id,
                            infr,
                            consulta_id,
                            vehiculo_id=vid,
                        )

                for obl in plan_norm.obligaciones_simit:
                    vid = vehiculo_ids.get(obl.placa) if obl.placa else None
                    if vid is None and vehiculo_consulta_id is not None:
                        vid = vehiculo_consulta_id
                    self._upsert_obligacion_simit(
                        conn,
                        obl,
                        consulta_id,
                        persona_id=persona_id,
                        vehiculo_id=vid,
                    )

                for acu in plan_norm.acuerdos_pago_simit:
                    self._upsert_acuerdo_pago_simit(
                        conn,
                        acu,
                        consulta_id,
                        persona_id=persona_id,
                        vehiculo_id=vehiculo_consulta_id,
                    )

                if persona_id is not None or vehiculo_consulta_id is not None:
                    self._actualizar_fks_consulta(
                        conn,
                        consulta_id,
                        persona_id=persona_id,
                        vehiculo_id=vehiculo_consulta_id,
                    )

                logger.info(
                    "Normalización B/C OK consulta_id=%s persona_id=%s "
                    "vehiculo_id=%s obligaciones=%s licencias=%s",
                    consulta_id,
                    persona_id,
                    vehiculo_consulta_id,
                    len(plan_norm.obligaciones_simit),
                    len(plan_norm.licencias),
                )
                return {
                    "persona_id": persona_id,
                    "vehiculo_id": vehiculo_consulta_id,
                }
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error(
                "Error SQL en normalización consulta_id=%s: %s",
                consulta_id,
                exc,
                exc_info=True,
            )
            raise PersistenciaError(
                f"No se pudo normalizar maestros/hechos: {exc}",
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

    def _upsert_persona(
        self,
        conn: psycopg.Connection,
        fila: FilaPersona,
        consulta_id: UUID,
    ) -> UUID:
        row = conn.execute(
            """
            insert into public.personas (
                tipo_documento, numero_documento, nombre_completo,
                estado_persona, numero_inscripcion_runt, fecha_inscripcion_runt,
                atributos, last_consulta_id, last_seen_at
            ) values (
                %(tipo_documento)s, %(numero_documento)s, %(nombre_completo)s,
                %(estado_persona)s, %(numero_inscripcion_runt)s,
                %(fecha_inscripcion_runt)s, %(atributos)s, %(consulta_id)s,
                timezone('utc', now())
            )
            on conflict (tipo_documento, numero_documento) do update set
                nombre_completo = coalesce(
                    excluded.nombre_completo, personas.nombre_completo
                ),
                estado_persona = coalesce(
                    excluded.estado_persona, personas.estado_persona
                ),
                numero_inscripcion_runt = coalesce(
                    excluded.numero_inscripcion_runt,
                    personas.numero_inscripcion_runt
                ),
                fecha_inscripcion_runt = coalesce(
                    excluded.fecha_inscripcion_runt,
                    personas.fecha_inscripcion_runt
                ),
                atributos = personas.atributos || excluded.atributos,
                last_consulta_id = excluded.last_consulta_id,
                last_seen_at = timezone('utc', now())
            returning id
            """,
            {
                "tipo_documento": fila.tipo_documento,
                "numero_documento": fila.numero_documento,
                "nombre_completo": fila.nombre_completo,
                "estado_persona": fila.estado_persona,
                "numero_inscripcion_runt": fila.numero_inscripcion_runt,
                "fecha_inscripcion_runt": fila.fecha_inscripcion_runt,
                "atributos": Jsonb(to_jsonable(fila.atributos) or {}),
                "consulta_id": consulta_id,
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_vehiculo(
        self,
        conn: psycopg.Connection,
        fila: FilaVehiculo,
        consulta_id: UUID,
    ) -> UUID:
        row = conn.execute(
            """
            insert into public.vehiculos (
                placa, atributos, last_consulta_id, last_seen_at
            ) values (
                %(placa)s, %(atributos)s, %(consulta_id)s, timezone('utc', now())
            )
            on conflict (placa) do update set
                atributos = vehiculos.atributos || excluded.atributos,
                last_consulta_id = excluded.last_consulta_id,
                last_seen_at = timezone('utc', now())
            returning id
            """,
            {
                "placa": fila.placa,
                "atributos": Jsonb(to_jsonable(fila.atributos) or {}),
                "consulta_id": consulta_id,
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_persona_vehiculo(
        self,
        conn: psycopg.Connection,
        *,
        persona_id: UUID,
        vehiculo_id: UUID,
        fuente: str,
        consulta_id: UUID,
    ) -> None:
        conn.execute(
            """
            insert into public.persona_vehiculo (
                persona_id, vehiculo_id, fuente, last_consulta_id, last_seen_at
            ) values (
                %(persona_id)s, %(vehiculo_id)s, %(fuente)s, %(consulta_id)s,
                timezone('utc', now())
            )
            on conflict (persona_id, vehiculo_id) do update set
                last_consulta_id = excluded.last_consulta_id,
                last_seen_at = timezone('utc', now())
            """,
            {
                "persona_id": persona_id,
                "vehiculo_id": vehiculo_id,
                "fuente": fuente,
                "consulta_id": consulta_id,
            },
        )

    def _upsert_licencia(
        self,
        conn: psycopg.Connection,
        persona_id: UUID,
        fila: FilaLicencia,
        consulta_id: UUID,
    ) -> UUID:
        attrs = Jsonb(to_jsonable(fila.atributos) or {})
        params = {
            "persona_id": persona_id,
            "numero_licencia": fila.numero_licencia,
            "categoria": fila.categoria,
            "estado": fila.estado,
            "fecha_expedicion": fila.fecha_expedicion,
            "fecha_vencimiento": fila.fecha_vencimiento,
            "atributos": attrs,
            "fuente": fila.fuente,
            "consulta_id": consulta_id,
        }
        if fila.numero_licencia is not None:
            row = conn.execute(
                """
                insert into public.licencias (
                    persona_id, numero_licencia, categoria, estado,
                    fecha_expedicion, fecha_vencimiento, atributos, fuente,
                    last_consulta_id, last_seen_at
                ) values (
                    %(persona_id)s, %(numero_licencia)s, %(categoria)s, %(estado)s,
                    %(fecha_expedicion)s, %(fecha_vencimiento)s, %(atributos)s,
                    %(fuente)s, %(consulta_id)s, timezone('utc', now())
                )
                on conflict (persona_id, numero_licencia)
                    where numero_licencia is not null
                do update set
                    categoria = coalesce(excluded.categoria, licencias.categoria),
                    estado = coalesce(excluded.estado, licencias.estado),
                    fecha_expedicion = coalesce(
                        excluded.fecha_expedicion, licencias.fecha_expedicion
                    ),
                    fecha_vencimiento = coalesce(
                        excluded.fecha_vencimiento, licencias.fecha_vencimiento
                    ),
                    atributos = licencias.atributos || excluded.atributos,
                    last_consulta_id = excluded.last_consulta_id,
                    last_seen_at = timezone('utc', now())
                returning id
                """,
                params,
            ).fetchone()
        else:
            # UK parcial por md5(atributos): lookup manual + insert/update.
            existing = conn.execute(
                """
                select id from public.licencias
                 where persona_id = %(persona_id)s
                   and numero_licencia is null
                   and md5(atributos::text) = md5(%(atributos)s::text)
                 limit 1
                """,
                {"persona_id": persona_id, "atributos": attrs},
            ).fetchone()
            if existing:
                row = conn.execute(
                    """
                    update public.licencias
                       set categoria = coalesce(%(categoria)s, categoria),
                           estado = coalesce(%(estado)s, estado),
                           fecha_expedicion = coalesce(
                               %(fecha_expedicion)s, fecha_expedicion
                           ),
                           fecha_vencimiento = coalesce(
                               %(fecha_vencimiento)s, fecha_vencimiento
                           ),
                           atributos = atributos || %(atributos)s,
                           last_consulta_id = %(consulta_id)s,
                           last_seen_at = timezone('utc', now())
                     where id = %(id)s
                    returning id
                    """,
                    {**params, "id": existing["id"]},
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    insert into public.licencias (
                        persona_id, numero_licencia, categoria, estado,
                        fecha_expedicion, fecha_vencimiento, atributos, fuente,
                        last_consulta_id, last_seen_at
                    ) values (
                        %(persona_id)s, null, %(categoria)s, %(estado)s,
                        %(fecha_expedicion)s, %(fecha_vencimiento)s, %(atributos)s,
                        %(fuente)s, %(consulta_id)s, timezone('utc', now())
                    )
                    returning id
                    """,
                    params,
                ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_infraccion_runt(
        self,
        conn: psycopg.Connection,
        persona_id: UUID,
        fila: FilaInfraccionRunt,
        consulta_id: UUID,
        *,
        vehiculo_id: Optional[UUID],
    ) -> UUID:
        row = conn.execute(
            """
            insert into public.infracciones_runt (
                persona_id, placa, vehiculo_id, descripcion, estado, fecha,
                valor, atributos, fingerprint, last_consulta_id, last_seen_at
            ) values (
                %(persona_id)s, %(placa)s, %(vehiculo_id)s, %(descripcion)s,
                %(estado)s, %(fecha)s, %(valor)s, %(atributos)s, %(fingerprint)s,
                %(consulta_id)s, timezone('utc', now())
            )
            on conflict (persona_id, fingerprint) do update set
                placa = coalesce(excluded.placa, infracciones_runt.placa),
                vehiculo_id = coalesce(
                    excluded.vehiculo_id, infracciones_runt.vehiculo_id
                ),
                descripcion = coalesce(
                    excluded.descripcion, infracciones_runt.descripcion
                ),
                estado = coalesce(excluded.estado, infracciones_runt.estado),
                fecha = coalesce(excluded.fecha, infracciones_runt.fecha),
                valor = coalesce(excluded.valor, infracciones_runt.valor),
                atributos = infracciones_runt.atributos || excluded.atributos,
                last_consulta_id = excluded.last_consulta_id,
                last_seen_at = timezone('utc', now())
            returning id
            """,
            {
                "persona_id": persona_id,
                "placa": fila.placa,
                "vehiculo_id": vehiculo_id,
                "descripcion": fila.descripcion,
                "estado": fila.estado,
                "fecha": fila.fecha,
                "valor": fila.valor,
                "atributos": Jsonb(to_jsonable(fila.atributos) or {}),
                "fingerprint": fila.fingerprint,
                "consulta_id": consulta_id,
            },
        ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_obligacion_simit(
        self,
        conn: psycopg.Connection,
        fila: FilaObligacionSimit,
        consulta_id: UUID,
        *,
        persona_id: Optional[UUID],
        vehiculo_id: Optional[UUID],
    ) -> UUID:
        params = {
            "numero": fila.numero,
            "tipo": fila.tipo,
            "persona_id": persona_id,
            "vehiculo_id": vehiculo_id,
            "fecha_imposicion": fila.fecha_imposicion,
            "notificacion": fila.notificacion,
            "secretaria": fila.secretaria,
            "infraccion": fila.infraccion,
            "infraccion_descripcion": fila.infraccion_descripcion,
            "estado": fila.estado,
            "valor": fila.valor,
            "valor_a_pagar": fila.valor_a_pagar,
            "atributos": Jsonb(to_jsonable(fila.atributos) or {}),
            "fingerprint": fila.fingerprint,
            "fuente": fila.fuente,
            "consulta_id": consulta_id,
        }
        if fila.numero is not None:
            row = conn.execute(
                """
                insert into public.obligaciones_simit (
                    numero, tipo, persona_id, vehiculo_id, fecha_imposicion,
                    notificacion, secretaria, infraccion, infraccion_descripcion,
                    estado, valor, valor_a_pagar, atributos, fingerprint, fuente,
                    last_consulta_id, last_seen_at, activo_en_ultima_consulta
                ) values (
                    %(numero)s, %(tipo)s, %(persona_id)s, %(vehiculo_id)s,
                    %(fecha_imposicion)s, %(notificacion)s, %(secretaria)s,
                    %(infraccion)s, %(infraccion_descripcion)s, %(estado)s,
                    %(valor)s, %(valor_a_pagar)s, %(atributos)s, %(fingerprint)s,
                    %(fuente)s, %(consulta_id)s, timezone('utc', now()), true
                )
                on conflict (numero) where numero is not null
                do update set
                    tipo = coalesce(excluded.tipo, obligaciones_simit.tipo),
                    persona_id = coalesce(
                        excluded.persona_id, obligaciones_simit.persona_id
                    ),
                    vehiculo_id = coalesce(
                        excluded.vehiculo_id, obligaciones_simit.vehiculo_id
                    ),
                    fecha_imposicion = coalesce(
                        excluded.fecha_imposicion,
                        obligaciones_simit.fecha_imposicion
                    ),
                    notificacion = coalesce(
                        excluded.notificacion, obligaciones_simit.notificacion
                    ),
                    secretaria = coalesce(
                        excluded.secretaria, obligaciones_simit.secretaria
                    ),
                    infraccion = coalesce(
                        excluded.infraccion, obligaciones_simit.infraccion
                    ),
                    infraccion_descripcion = coalesce(
                        excluded.infraccion_descripcion,
                        obligaciones_simit.infraccion_descripcion
                    ),
                    estado = coalesce(excluded.estado, obligaciones_simit.estado),
                    valor = coalesce(excluded.valor, obligaciones_simit.valor),
                    valor_a_pagar = coalesce(
                        excluded.valor_a_pagar, obligaciones_simit.valor_a_pagar
                    ),
                    atributos = obligaciones_simit.atributos || excluded.atributos,
                    last_consulta_id = excluded.last_consulta_id,
                    last_seen_at = timezone('utc', now()),
                    activo_en_ultima_consulta = true
                returning id
                """,
                params,
            ).fetchone()
        else:
            row = conn.execute(
                """
                insert into public.obligaciones_simit (
                    numero, tipo, persona_id, vehiculo_id, fecha_imposicion,
                    notificacion, secretaria, infraccion, infraccion_descripcion,
                    estado, valor, valor_a_pagar, atributos, fingerprint, fuente,
                    last_consulta_id, last_seen_at, activo_en_ultima_consulta
                ) values (
                    null, %(tipo)s, %(persona_id)s, %(vehiculo_id)s,
                    %(fecha_imposicion)s, %(notificacion)s, %(secretaria)s,
                    %(infraccion)s, %(infraccion_descripcion)s, %(estado)s,
                    %(valor)s, %(valor_a_pagar)s, %(atributos)s, %(fingerprint)s,
                    %(fuente)s, %(consulta_id)s, timezone('utc', now()), true
                )
                on conflict (fingerprint)
                    where numero is null and fingerprint is not null
                do update set
                    tipo = coalesce(excluded.tipo, obligaciones_simit.tipo),
                    persona_id = coalesce(
                        excluded.persona_id, obligaciones_simit.persona_id
                    ),
                    vehiculo_id = coalesce(
                        excluded.vehiculo_id, obligaciones_simit.vehiculo_id
                    ),
                    atributos = obligaciones_simit.atributos || excluded.atributos,
                    last_consulta_id = excluded.last_consulta_id,
                    last_seen_at = timezone('utc', now()),
                    activo_en_ultima_consulta = true
                returning id
                """,
                params,
            ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _upsert_acuerdo_pago_simit(
        self,
        conn: psycopg.Connection,
        fila: FilaAcuerdoPagoSimit,
        consulta_id: UUID,
        *,
        persona_id: Optional[UUID],
        vehiculo_id: Optional[UUID],
    ) -> UUID:
        params = {
            "numero_acuerdo": fila.numero_acuerdo,
            "persona_id": persona_id,
            "vehiculo_id": vehiculo_id,
            "estado": fila.estado,
            "valor": fila.valor,
            "atributos": Jsonb(to_jsonable(fila.atributos) or {}),
            "fingerprint": fila.fingerprint,
            "fuente": fila.fuente,
            "consulta_id": consulta_id,
        }
        if fila.numero_acuerdo is not None:
            row = conn.execute(
                """
                insert into public.acuerdos_pago_simit (
                    numero_acuerdo, persona_id, vehiculo_id, estado, valor,
                    atributos, fingerprint, fuente, last_consulta_id,
                    last_seen_at, activo_en_ultima_consulta
                ) values (
                    %(numero_acuerdo)s, %(persona_id)s, %(vehiculo_id)s,
                    %(estado)s, %(valor)s, %(atributos)s, %(fingerprint)s,
                    %(fuente)s, %(consulta_id)s, timezone('utc', now()), true
                )
                on conflict (numero_acuerdo) where numero_acuerdo is not null
                do update set
                    persona_id = coalesce(
                        excluded.persona_id, acuerdos_pago_simit.persona_id
                    ),
                    vehiculo_id = coalesce(
                        excluded.vehiculo_id, acuerdos_pago_simit.vehiculo_id
                    ),
                    estado = coalesce(excluded.estado, acuerdos_pago_simit.estado),
                    valor = coalesce(excluded.valor, acuerdos_pago_simit.valor),
                    atributos = acuerdos_pago_simit.atributos || excluded.atributos,
                    last_consulta_id = excluded.last_consulta_id,
                    last_seen_at = timezone('utc', now()),
                    activo_en_ultima_consulta = true
                returning id
                """,
                params,
            ).fetchone()
        else:
            row = conn.execute(
                """
                insert into public.acuerdos_pago_simit (
                    numero_acuerdo, persona_id, vehiculo_id, estado, valor,
                    atributos, fingerprint, fuente, last_consulta_id,
                    last_seen_at, activo_en_ultima_consulta
                ) values (
                    null, %(persona_id)s, %(vehiculo_id)s, %(estado)s, %(valor)s,
                    %(atributos)s, %(fingerprint)s, %(fuente)s, %(consulta_id)s,
                    timezone('utc', now()), true
                )
                on conflict (fingerprint)
                    where numero_acuerdo is null and fingerprint is not null
                do update set
                    persona_id = coalesce(
                        excluded.persona_id, acuerdos_pago_simit.persona_id
                    ),
                    vehiculo_id = coalesce(
                        excluded.vehiculo_id, acuerdos_pago_simit.vehiculo_id
                    ),
                    atributos = acuerdos_pago_simit.atributos || excluded.atributos,
                    last_consulta_id = excluded.last_consulta_id,
                    last_seen_at = timezone('utc', now()),
                    activo_en_ultima_consulta = true
                returning id
                """,
                params,
            ).fetchone()
        assert row is not None
        return as_uuid(row["id"])

    def _actualizar_fks_consulta(
        self,
        conn: psycopg.Connection,
        consulta_id: UUID,
        *,
        persona_id: Optional[UUID],
        vehiculo_id: Optional[UUID],
    ) -> None:
        conn.execute(
            """
            update public.consultas
               set persona_id = coalesce(%(persona_id)s, persona_id),
                   vehiculo_id = coalesce(%(vehiculo_id)s, vehiculo_id)
             where id = %(id)s
            """,
            {
                "id": consulta_id,
                "persona_id": persona_id,
                "vehiculo_id": vehiculo_id,
            },
        )

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
