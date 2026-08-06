#!/usr/bin/env python3
"""
Ejecuta la verificación E2E de maestros/upserts v2 (F-05) y imprime un reporte.

Uso (desde la raíz del repo):
  export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
  # Migraciones F-01 aplicadas (./scripts/apply_local_migrations.sh)
  python scripts/verificar_maestros_upsert_e2e.py

Código de salida: 0 si todos los escenarios pytest F-05 pasan.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"=== Verificación maestros/upserts E2E (F-05) — {stamp} ===", flush=True)
    print(f"Repo: {ROOT}", flush=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_maestros_upsert_e2e.py",
        "-v",
        "--tb=short",
    ]
    print("Comando:", " ".join(cmd), flush=True)
    print(flush=True)
    completed = subprocess.run(cmd, cwd=ROOT)
    print(flush=True)
    if completed.returncode == 0:
        print("RESULTADO GLOBAL: PASS", flush=True)
        print("Registrar en docs/VALIDACION_MAESTROS_UPSERT.md si aplica.", flush=True)
    else:
        print("RESULTADO GLOBAL: FAIL", flush=True)
        print("Revisar salida pytest y docs/VALIDACION_MAESTROS_UPSERT.md.", flush=True)
        print(
            "Si skip por BD: confirma Docker + DATABASE_URL + migraciones F-01.",
            flush=True,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
