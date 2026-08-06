"""Tests de espera SIMIT (F-04) — sin navegador real."""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from services import simit_playwright as sp


class _FakeFirst:
    def __init__(self, waits: List[dict[str, Any]], *, raise_timeout: bool = False) -> None:
        self._waits = waits
        self._raise_timeout = raise_timeout

    def wait_for(self, *, state: str, timeout: int) -> None:
        self._waits.append({"state": state, "timeout": timeout})
        if self._raise_timeout:
            raise sp.PWTimeoutError("fake timeout")


class _FakeReadyLocator:
    def __init__(self, waits: List[dict[str, Any]], *, raise_timeout: bool = False) -> None:
        self.first = _FakeFirst(waits, raise_timeout=raise_timeout)


def test_wait_for_results_una_sola_espera_compartida(monkeypatch: pytest.MonkeyPatch) -> None:
    """No debe encadenar N timeouts completos; un solo wait_for."""
    waits: List[dict[str, Any]] = []
    page = MagicMock()
    page.wait_for_timeout = MagicMock()

    monkeypatch.setattr(
        sp,
        "results_ready_locator",
        lambda _page: _FakeReadyLocator(waits),
    )
    monkeypatch.setattr(sp, "sin_pendientes_visible", lambda _page: True)

    sp.wait_for_results(page, debug=True, timeout_ms=12_000)

    assert len(waits) == 1
    assert waits[0]["timeout"] == 12_000
    assert waits[0]["state"] == "visible"
    page.wait_for_timeout.assert_called_once_with(sp._SETTLE_MS_OK)


def test_wait_for_results_timeout_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: List[dict[str, Any]] = []
    page = MagicMock()
    page.wait_for_timeout = MagicMock()

    monkeypatch.setattr(
        sp,
        "results_ready_locator",
        lambda _page: _FakeReadyLocator(waits, raise_timeout=True),
    )

    sp.wait_for_results(page, debug=True, timeout_ms=5_000)

    assert len(waits) == 1
    page.wait_for_timeout.assert_called_once_with(sp._SETTLE_MS_FALLBACK)


def test_results_ready_locator_encadena_or() -> None:
    """Contrato: tablas + mensajes sin pendientes en un locator compuesto."""
    page = MagicMock()
    base = MagicMock(name="base")
    page.locator.return_value = base
    page.get_by_text.return_value = MagicMock(name="text")
    base.or_.return_value = base

    loc = sp.results_ready_locator(page)

    assert loc is base
    assert page.locator.call_count == 3
    page.locator.assert_any_call(sp.SELECTOR_RESUMEN_ESTADO)
    page.locator.assert_any_call(sp.SELECTOR_MULTA_TABLE)
    page.locator.assert_any_call(sp.SELECTOR_ACUERDO_TABLE)
    assert page.get_by_text.call_count == 2
    assert base.or_.call_count == 4


def test_re_sin_pendientes_cubre_mensajes_conocidos() -> None:
    assert sp.RE_SIN_PENDIENTES.search(
        "No tienes comparendos ni multas pendientes por pagar"
    )
    assert sp.RE_SIN_PENDIENTES.search(
        "El ciudadano no posee a la fecha pendientes con el SIMIT"
    )
