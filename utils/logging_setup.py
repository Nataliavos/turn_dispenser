"""
Configuración de logging de la aplicación (RF-19).

Formato con correlation_id, nivel y archivo opcionales desde settings.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Optional
from uuid import uuid4

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_configured: bool = False

_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s | "
    "cid=%(correlation_id)s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class CorrelationFilter(logging.Filter):
    """Inyecta correlation_id en cada LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        return True


def new_correlation_id() -> str:
    """Identificador corto por consulta (12 hex)."""
    return uuid4().hex[:12]


def set_correlation_id(value: Optional[str]) -> None:
    """Asocia el id de correlación al contexto actual (hilo/async)."""
    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()


def ensure_correlation_id() -> str:
    """Reutiliza el cid actual o crea uno nuevo."""
    current = get_correlation_id()
    if current:
        return current
    created = new_correlation_id()
    set_correlation_id(created)
    return created


def _resolve_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    *,
    force: bool = False,
) -> None:
    """
    Configura el logging raíz de la app una sola vez.

    Defaults conservadores: consola a INFO (o el nivel de settings).
    Archivo solo si ``log_file`` / ``LOG_FILE`` está definido.
    """
    global _configured
    if _configured and not force:
        return

    from config.settings import get_settings

    settings = get_settings()
    if level is None:
        level = settings.log_level
    if log_file is None:
        log_file = settings.log_file

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_resolve_level(level))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    correlation = CorrelationFilter()

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    console.addFilter(correlation)
    root.addHandler(console)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(correlation)
        root.addHandler(file_handler)

    # Menos ruido de librerías de terceros
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).debug(
        "Logging configurado level=%s file=%s",
        level,
        log_file or "(consola)",
    )


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger de módulo (tras ``setup_logging`` en entry points)."""
    return logging.getLogger(name)
