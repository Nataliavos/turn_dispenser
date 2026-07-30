#!/usr/bin/env python3
"""
Ejecuta la batería automatizada de pruebas integrales (E-02).

Uso (desde la raíz del repo):
  export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
  python scripts/verificar_flujo_integral.py

Nivel A (siempre): smoke imports + unitarios + flujo integral mockeado.
Nivel D (si DATABASE_URL/Docker responde): persistencia E2E (D-04).

Código de salida: 0 solo si todos los niveles ejecutados pasan.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Suites sin dependencia de Postgres.
_SUITES_OFFLINE = [
    "tests/test_documento_validator.py",
    "tests/test_modelos_dominio.py",
    "tests/test_errores_fuentes.py",
    "tests/test_parse_helpers.py",
    "tests/test_runt_parser.py",
    "tests/test_simit_parser.py",
    "tests/test_persistencia_mappers.py",
    "tests/test_persistencia_post_consulta.py",
    "tests/test_flujo_integral.py",
]

_SUITE_PERSISTENCIA = "tests/test_persistencia_e2e.py"


def _run(cmd: list[str], *, titulo: str) -> int:
    print(f"\n--- {titulo} ---", flush=True)
    print("Comando:", " ".join(cmd), flush=True)
    completed = subprocess.run(cmd, cwd=ROOT)
    estado = "PASS" if completed.returncode == 0 else "FAIL"
    print(f"Resultado {titulo}: {estado}", flush=True)
    return completed.returncode


def _db_disponible() -> bool:
    code = (
        "from config.settings import clear_settings_cache, get_settings\n"
        "from repositories import get_database, reset_database\n"
        "from repositories.exceptions import ConexionPersistenciaError, PersistenciaError\n"
        "clear_settings_cache(); reset_database()\n"
        "s = get_settings()\n"
        "ok = False\n"
        "if s.database_url:\n"
        "    try:\n"
        "        ok = get_database(s).ping()\n"
        "    except (PersistenciaError, ConexionPersistenciaError):\n"
        "        ok = False\n"
        "raise SystemExit(0 if ok else 1)\n"
    )
    return (
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"=== Verificación flujo integral (E-02) — {stamp} ===", flush=True)
    print(f"Repo: {ROOT}", flush=True)

    # Smoke de imports críticos
    rc_smoke = _run(
        [
            sys.executable,
            "-c",
            "from controllers.consulta_controller import ConsultaController\n"
            "from views.gui_qt import MainWindow\n"
            "from views.resultado_formatter import formatear_resultado_consulta\n"
            "from config.settings import get_settings\n"
            "get_settings()\n"
            "print('smoke imports OK')\n",
        ],
        titulo="A1 smoke imports",
    )

    rc_offline = _run(
        [sys.executable, "-m", "pytest", *_SUITES_OFFLINE, "-v", "--tb=short"],
        titulo="A2 suites offline / flujo mock",
    )

    db_ok = _db_disponible()
    if db_ok:
        rc_db = _run(
            [
                sys.executable,
                "-m",
                "pytest",
                _SUITE_PERSISTENCIA,
                "-v",
                "--tb=short",
            ],
            titulo="D1 persistencia E2E (D-04)",
        )
    else:
        print(
            "\n--- D1 persistencia E2E (D-04) ---\n"
            "OMITIDO: Postgres Supabase local no disponible "
            "(export DATABASE_URL=... y docker ps).\n"
            "Ver docs/VALIDACION_PERSISTENCIA.md",
            flush=True,
        )
        rc_db = 0  # no falla el script; el acta debe marcar OMITIDO

    print(flush=True)
    fallos = [n for n, c in (
        ("A1", rc_smoke),
        ("A2", rc_offline),
        ("D1", rc_db if db_ok else 0),
    ) if c != 0]

    if fallos:
        print(f"RESULTADO GLOBAL: FAIL ({', '.join(fallos)})", flush=True)
        print("Registrar en docs/PRUEBAS_INTEGRALES.md.", flush=True)
        return 1

    if not db_ok:
        print(
            "RESULTADO GLOBAL: PASS_PARCIAL "
            "(offline OK; persistencia E2E omitida)",
            flush=True,
        )
    else:
        print("RESULTADO GLOBAL: PASS", flush=True)
    print("Registrar ejecución en docs/PRUEBAS_INTEGRALES.md.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
