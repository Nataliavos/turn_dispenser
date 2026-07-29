"""Utilidades compartidas para tests de parsers (C-02)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "fixtures"


def load_fixture(*parts: str) -> str:
    """Carga un fixture HTML relativo a ``fixtures/``."""
    path = FIXTURES_DIR.joinpath(*parts)
    if not path.is_file():
        raise FileNotFoundError(f"Fixture no encontrado: {path}")
    return path.read_text(encoding="utf-8")


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
