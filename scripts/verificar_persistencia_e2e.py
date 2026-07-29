#!/usr/bin/env python3
"""
Ejecuta la verificación E2E de persistencia (D-04) y imprime un reporte.

Uso (desde la raíz del repo):
  export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
  python scripts/verificar_persistencia_e2e.py

Código de salida: 0 si todos los escenarios pytest E2E pasan.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"=== Verificación persistencia E2E (D-04) — {stamp} ===", flush=True)
    print(f"Repo: {ROOT}", flush=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_persistencia_e2e.py",
        "-v",
        "--tb=short",
    ]
    print("Comando:", " ".join(cmd), flush=True)
    print(flush=True)
    completed = subprocess.run(cmd, cwd=ROOT)
    print(flush=True)
    if completed.returncode == 0:
        print("RESULTADO GLOBAL: PASS", flush=True)
        print("Registrar en docs/VALIDACION_PERSISTENCIA.md si aplica.", flush=True)
    else:
        print("RESULTADO GLOBAL: FAIL", flush=True)
        print("Revisar salida pytest y docs/VALIDACION_PERSISTENCIA.md.", flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
