"""
Carga de configuración desde variables de entorno + defaults seguros.

Los valores por defecto preservan el comportamiento actual de la app
(navegador visible para CAPTCHA RUNT, slow_mo y timeouts conocidos).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_RUNT_URL = (
    "https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento"
    "/consulta/consulta-ciudadano-documento"
)
_DEFAULT_SIMIT_URL = "https://www.fcm.org.co/simit/#/home-public"


def _env_str(key: str, default: str) -> str:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _env_optional_str(key: str) -> Optional[str]:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


def _load_env_files() -> None:
    """Carga `.env` y, si existe, `.env.local` (override)."""
    load_dotenv(_PROJECT_ROOT / ".env")
    load_dotenv(_PROJECT_ROOT / ".env.local", override=True)


@dataclass(frozen=True)
class Settings:
    """Parámetros de runtime de Turn Dispenser."""

    app_env: str
    debug: bool

    log_level: str
    log_file: Optional[str]

    runt_url: str
    simit_url: str

    browser_headless: bool
    runt_slow_mo_ms: int
    simit_slow_mo_ms: int

    navigation_timeout_ms: int
    runt_network_idle_timeout_ms: int
    simit_network_idle_timeout_ms: int
    simit_results_timeout_ms: int
    runt_captcha_timeout_ms: int

    # Persistencia (D-01/D-02): Postgres del stack Supabase local.
    database_url: Optional[str]
    db_connect_timeout_s: int
    supabase_url: Optional[str]
    supabase_anon_key: Optional[str]
    supabase_service_role_key: Optional[str]


def _default_log_level(debug: bool) -> str:
    """Si LOG_LEVEL no está definido: DEBUG con debug=true, INFO en caso contrario."""
    explicit = os.getenv("LOG_LEVEL")
    if explicit is not None and explicit.strip() != "":
        return explicit.strip().upper()
    return "DEBUG" if debug else "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración cargada (cacheada por proceso)."""
    _load_env_files()
    debug = _env_bool("DEBUG", True)
    return Settings(
        app_env=_env_str("APP_ENV", "local"),
        debug=debug,
        log_level=_default_log_level(debug),
        log_file=_env_optional_str("LOG_FILE"),
        runt_url=_env_str("RUNT_URL", _DEFAULT_RUNT_URL),
        simit_url=_env_str("SIMIT_URL", _DEFAULT_SIMIT_URL),
        browser_headless=_env_bool("BROWSER_HEADLESS", False),
        runt_slow_mo_ms=_env_int("RUNT_SLOW_MO_MS", 300),
        simit_slow_mo_ms=_env_int("SIMIT_SLOW_MO_MS", 200),
        navigation_timeout_ms=_env_int("NAVIGATION_TIMEOUT_MS", 60_000),
        runt_network_idle_timeout_ms=_env_int("RUNT_NETWORK_IDLE_TIMEOUT_MS", 10_000),
        simit_network_idle_timeout_ms=_env_int(
            "SIMIT_NETWORK_IDLE_TIMEOUT_MS", 15_000
        ),
        simit_results_timeout_ms=_env_int("SIMIT_RESULTS_TIMEOUT_MS", 30_000),
        runt_captcha_timeout_ms=_env_int("RUNT_CAPTCHA_TIMEOUT_MS", 45_000),
        database_url=_env_optional_str("DATABASE_URL"),
        db_connect_timeout_s=_env_int("DB_CONNECT_TIMEOUT_S", 10),
        supabase_url=_env_optional_str("SUPABASE_URL"),
        supabase_anon_key=_env_optional_str("SUPABASE_ANON_KEY"),
        supabase_service_role_key=_env_optional_str("SUPABASE_SERVICE_ROLE_KEY"),
    )


def clear_settings_cache() -> None:
    """Invalida la caché (útil en tests o recarga manual)."""
    get_settings.cache_clear()
