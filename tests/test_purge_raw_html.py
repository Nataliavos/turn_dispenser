"""Tests unitarios retención raw_html F-07 (sin BD / con mocks)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from repositories.exceptions import PersistenciaError
from repositories.purge_raw_html import (
    cutoff_utc,
    ejecutar_purge_raw_html,
)


def test_cutoff_utc_resta_dias() -> None:
    now = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    assert cutoff_utc(30, now=now) == datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_cutoff_days_invalidos() -> None:
    with pytest.raises(ValueError):
        cutoff_utc(0)


def test_dry_run_no_ejecuta_update(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    monkeypatch.setattr(
        "repositories.purge_raw_html.contar_candidatas_raw_html",
        lambda _repo, *, cutoff: (3, 2),
    )
    resumen = ejecutar_purge_raw_html(repo, days=30, dry_run=True)
    assert resumen.candidatas_runt == 3
    assert resumen.candidatas_simit == 2
    assert resumen.actualizadas_total == 0
    assert not resumen.errores
    # No abre connection para UPDATE
    repo._db.connection.assert_not_called()


def test_ejecucion_real_nullifica(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    conn = MagicMock()
    repo._db.connection.return_value.__enter__.return_value = conn
    cur_r = MagicMock(rowcount=4)
    cur_s = MagicMock(rowcount=1)
    conn.execute.side_effect = [cur_r, cur_s]

    monkeypatch.setattr(
        "repositories.purge_raw_html.contar_candidatas_raw_html",
        lambda _repo, *, cutoff: (4, 1),
    )

    resumen = ejecutar_purge_raw_html(repo, days=30, dry_run=False)
    assert resumen.actualizadas_runt == 4
    assert resumen.actualizadas_simit == 1
    assert conn.execute.call_count == 2
    assert not resumen.errores


def test_conteo_falla_reporta_error(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()

    def _boom(*_a, **_k):
        raise PersistenciaError("sin BD")

    monkeypatch.setattr(
        "repositories.purge_raw_html.contar_candidatas_raw_html",
        _boom,
    )
    resumen = ejecutar_purge_raw_html(repo, days=7, dry_run=True)
    assert resumen.errores
    assert "sin BD" in resumen.errores[0]
