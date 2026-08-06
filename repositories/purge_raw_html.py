"""
Retención F-07: nullificar ``raw_html`` antiguo en snapshots (PII).

No toca maestros ni hechos tipados. Preferir NULL sobre borrar filas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from repositories.consulta_repository import ConsultaRepository
from repositories.exceptions import PersistenciaError
from utils.logging_setup import get_logger

DEFAULT_RETENTION_DAYS = 30

_SQL_COUNT = """
select
  (
    select count(*)::int
      from public.resultados_runt r
      join public.consultas c on c.id = r.consulta_id
     where r.raw_html is not null
       and coalesce(c.finalizado_en, c.iniciado_en, r.created_at)
           < %(cutoff)s
  ) as runt,
  (
    select count(*)::int
      from public.resultados_simit s
      join public.consultas c on c.id = s.consulta_id
     where s.raw_html is not null
       and coalesce(c.finalizado_en, c.iniciado_en, s.created_at)
           < %(cutoff)s
  ) as simit
"""

_SQL_NULLIFY_RUNT = """
update public.resultados_runt r
   set raw_html = null
  from public.consultas c
 where r.consulta_id = c.id
   and r.raw_html is not null
   and coalesce(c.finalizado_en, c.iniciado_en, r.created_at) < %(cutoff)s
"""

_SQL_NULLIFY_SIMIT = """
update public.resultados_simit s
   set raw_html = null
  from public.consultas c
 where s.consulta_id = c.id
   and s.raw_html is not null
   and coalesce(c.finalizado_en, c.iniciado_en, s.created_at) < %(cutoff)s
"""


@dataclass
class ResumenPurgeRawHtml:
    days: int
    cutoff: datetime
    dry_run: bool
    candidatas_runt: int = 0
    candidatas_simit: int = 0
    actualizadas_runt: int = 0
    actualizadas_simit: int = 0
    errores: List[str] = field(default_factory=list)

    @property
    def candidatas_total(self) -> int:
        return self.candidatas_runt + self.candidatas_simit

    @property
    def actualizadas_total(self) -> int:
        return self.actualizadas_runt + self.actualizadas_simit


def cutoff_utc(days: int, *, now: Optional[datetime] = None) -> datetime:
    if days < 1:
        raise ValueError("days debe ser >= 1")
    base = now or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base - timedelta(days=days)


def contar_candidatas_raw_html(
    repo: ConsultaRepository,
    *,
    cutoff: datetime,
) -> tuple[int, int]:
    """Retorna (runt, simit) filas con raw_html no nulo anteriores al cutoff."""
    try:
        with repo._db.connection() as conn:
            row = conn.execute(_SQL_COUNT, {"cutoff": cutoff}).fetchone()
        assert row is not None
        return int(row["runt"]), int(row["simit"])
    except Exception as exc:
        raise PersistenciaError(
            f"No se pudieron contar candidatas raw_html: {exc}",
            causa=exc if isinstance(exc, Exception) else None,
        ) from exc


def ejecutar_purge_raw_html(
    repo: ConsultaRepository,
    *,
    days: int = DEFAULT_RETENTION_DAYS,
    dry_run: bool = False,
    now: Optional[datetime] = None,
    log=None,
) -> ResumenPurgeRawHtml:
    """
    Nullifica ``raw_html`` en ``resultados_*`` fuera de la ventana de retención.

    Dry-run: solo cuenta. No elimina maestros/hechos ni filas de snapshot.
    """
    logger = log or get_logger(__name__)
    cutoff = cutoff_utc(days, now=now)
    resumen = ResumenPurgeRawHtml(days=days, cutoff=cutoff, dry_run=dry_run)

    try:
        runt_n, simit_n = contar_candidatas_raw_html(repo, cutoff=cutoff)
    except PersistenciaError as exc:
        resumen.errores.append(exc.mensaje)
        logger.error("%s", exc.mensaje)
        return resumen

    resumen.candidatas_runt = runt_n
    resumen.candidatas_simit = simit_n
    logger.info(
        "Purge raw_html F-07: days=%s cutoff=%s candidatas runt=%s simit=%s dry_run=%s",
        days,
        cutoff.isoformat(),
        runt_n,
        simit_n,
        dry_run,
    )

    if dry_run:
        logger.info(
            "[dry-run] no se modifica BD; %s fila(s) se nullificarían",
            resumen.candidatas_total,
        )
        return resumen

    try:
        with repo._db.connection() as conn:
            cur_r = conn.execute(_SQL_NULLIFY_RUNT, {"cutoff": cutoff})
            cur_s = conn.execute(_SQL_NULLIFY_SIMIT, {"cutoff": cutoff})
            resumen.actualizadas_runt = cur_r.rowcount if cur_r.rowcount is not None else 0
            resumen.actualizadas_simit = cur_s.rowcount if cur_s.rowcount is not None else 0
        logger.info(
            "Purge OK: nullificados runt=%s simit=%s (maestros/hechos intactos)",
            resumen.actualizadas_runt,
            resumen.actualizadas_simit,
        )
    except Exception as exc:
        msg = f"Error al nullificar raw_html: {exc}"
        resumen.errores.append(msg)
        logger.error("%s", msg, exc_info=True)

    return resumen
