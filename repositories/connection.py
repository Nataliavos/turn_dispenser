"""
Conexión mínima a Postgres del stack Supabase local.

Usa ``psycopg`` (v3) con SQL directo — sin ORM — vía ``DATABASE_URL``.
El rol ``postgres`` / ``service_role`` bypasa RLS (adecuado para la app de escritorio).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

import psycopg
from psycopg.rows import dict_row

from config.settings import Settings, get_settings
from repositories.exceptions import ConexionPersistenciaError, PersistenciaError
from utils.logging_setup import get_logger

logger = get_logger(__name__)

_database: Optional["Database"] = None


class Database:
    """Fábrica de conexiones a partir de settings (sin pool por ahora)."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    @property
    def database_url(self) -> str:
        url = self._settings.database_url
        if not url:
            raise ConexionPersistenciaError(
                "DATABASE_URL no está configurada. "
                "Copia .env.example a .env y define el DSN del Postgres local "
                "(ver docs/supabase-local.md)."
            )
        return url

    @property
    def connect_timeout_s(self) -> int:
        return self._settings.db_connect_timeout_s

    def connect(self) -> psycopg.Connection:
        """Abre una conexión nueva. El llamador debe cerrarla o usar ``connection()``."""
        try:
            conn = psycopg.connect(
                self.database_url,
                connect_timeout=self.connect_timeout_s,
                row_factory=dict_row,
                autocommit=False,
            )
        except PersistenciaError:
            raise
        except psycopg.Error as exc:
            logger.error(
                "Fallo de conexión a Postgres (Supabase local): %s",
                exc,
                exc_info=True,
            )
            raise ConexionPersistenciaError(
                "No se pudo conectar al Postgres de Supabase. "
                "¿Está Docker/`supabase start` activo? "
                f"Detalle: {exc}",
                causa=exc,
            ) from exc
        except Exception as exc:  # red / DNS inesperados
            logger.error(
                "Error inesperado al conectar a Postgres: %s",
                exc,
                exc_info=True,
            )
            raise ConexionPersistenciaError(
                f"Error inesperado de conexión a Postgres: {exc}",
                causa=exc,
            ) from exc
        logger.debug("Conexión Postgres abierta")
        return conn

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection, None, None]:
        """Context manager: commit al salir OK, rollback si hay error."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ping(self) -> bool:
        """True si ``SELECT 1`` responde."""
        with self.connection() as conn:
            row = conn.execute("select 1 as ok").fetchone()
            return bool(row and row.get("ok") == 1)


def get_database(settings: Optional[Settings] = None) -> Database:
    """Instancia compartida (o nueva si se pasan settings explícitos)."""
    global _database
    if settings is not None:
        return Database(settings)
    if _database is None:
        _database = Database()
    return _database


def reset_database() -> None:
    """Limpia el singleton (tests / recarga de settings)."""
    global _database
    _database = None
