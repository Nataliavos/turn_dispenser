"""
Helpers compartidos de automatización Playwright (RUNT / SIMIT).

Ticket C-03: una sola implementación de utilidades de localización.
"""

from __future__ import annotations

from typing import Callable, List, Union

from playwright.sync_api import Locator, Page, TimeoutError as PWTimeoutError

LocatorCandidate = Union[str, Callable[[Page], Locator]]


def pick_first_working_locator(
    page: Page,
    locator_candidates: List[LocatorCandidate],
    description: str = "elemento",
    *,
    timeout_ms: int = 5000,
) -> Locator:
    """
    Intenta encontrar un elemento con una lista de selectores/candidatos.

    Cada candidato puede ser:
    1) un string CSS (``input[name='numeroDocumento']``)
    2) una función ``(page) -> Locator`` (p. ej. ``lambda p: p.get_by_label(...)``)

    Retorna el primer locator visible. Útil en portales Angular/HTML inestable.
    """
    for css_or_getter in locator_candidates:
        try:
            loc = (
                css_or_getter(page)
                if callable(css_or_getter)
                else page.locator(css_or_getter)
            )
            loc.wait_for(state="visible", timeout=timeout_ms)
            return loc
        except PWTimeoutError:
            continue
        except Exception:
            continue
    raise RuntimeError(
        f"No se encontró {description}. Ajusta los selectores según el HTML real."
    )
