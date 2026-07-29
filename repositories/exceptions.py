"""Errores de la capa de persistencia."""

from __future__ import annotations

from typing import Optional


class PersistenciaError(Exception):
    """Fallo al leer o escribir hechos en la base de datos."""

    def __init__(self, mensaje: str, *, causa: Optional[BaseException] = None) -> None:
        self.mensaje = mensaje.strip()
        self.causa = causa
        super().__init__(self.mensaje)


class ConexionPersistenciaError(PersistenciaError):
    """No se pudo conectar al Postgres de Supabase (Docker caído, DSN inválido, etc.)."""
