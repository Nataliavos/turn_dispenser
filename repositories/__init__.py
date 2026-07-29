"""Capa de persistencia (M7) contra Postgres de Supabase local."""

from repositories.consulta_repository import ConsultaRepository
from repositories.connection import Database, get_database, reset_database
from repositories.exceptions import ConexionPersistenciaError, PersistenciaError

__all__ = [
    "ConsultaRepository",
    "ConexionPersistenciaError",
    "Database",
    "PersistenciaError",
    "get_database",
    "reset_database",
]
