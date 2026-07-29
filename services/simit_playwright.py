# services/simit_playwright.py
# Automatización del portal público SIMIT (https://www.fcm.org.co/simit/#/home-public)

import re
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from config.settings import get_settings
from services.playwright_helpers import pick_first_working_locator
from utils.logging_setup import get_logger

logger = get_logger(__name__)


def dismiss_promo_modal(page, debug: bool = True) -> None:
    """Cierra el modal promocional superpuesto (si aparece)."""
    try:
        close_candidates = [
            ".modal.show .close",
            ".modal-header .close",
            "button.close",
            lambda p: p.locator(".modal.show button").filter(has_text=re.compile(r"×|x", re.I)).first,
            lambda p: p.get_by_role("button", name=re.compile(r"cerrar|close|×", re.I)).first,
            "[aria-label='Close']",
            "[aria-label='Cerrar']",
        ]
        for cand in close_candidates:
            try:
                loc = cand(page) if callable(cand) else page.locator(cand)
                if loc.count() > 0 and loc.first.is_visible():
                    if debug:
                        logger.debug("Modal promocional detectado. Cerrando…")
                    loc.first.click()
                    page.wait_for_timeout(500)
                    if debug:
                        logger.debug("Modal promocional cerrado.")
                    return
            except Exception:
                continue
        if debug:
            logger.debug("No se detectó modal promocional.")
    except Exception as e:
        if debug:
            logger.warning("Error al cerrar modal promocional: %s", e)


def fill_search_input(page, identificador: str, debug: bool = True) -> None:
    if debug:
        logger.debug("Buscando campo de búsqueda para '%s'…", identificador)

    input_candidates = [
        "input[placeholder*='identificación' i]",
        "input[placeholder*='placa' i]",
        lambda p: p.get_by_placeholder(re.compile(r"identificación|placa", re.I)),
        "input.form-control",
        lambda p: p.locator("input[type='text']").first,
    ]
    input_loc = pick_first_working_locator(page, input_candidates, "campo de búsqueda SIMIT")
    input_loc.fill("")
    input_loc.fill(identificador)
    if debug:
        logger.debug("Identificador '%s' ingresado.", identificador)


def click_search_button(page, debug: bool = True) -> None:
    if debug:
        logger.debug("Buscando botón de consulta SIMIT…")

    button_candidates = [
        "button.btn-primary",
        ".input-group button",
        ".input-group-append button",
        lambda p: p.get_by_role("button").filter(has_text=re.compile(r"buscar|consultar", re.I)).first,
        "button[type='submit']",
        lambda p: p.locator("button.btn").first,
    ]
    btn = pick_first_working_locator(page, button_candidates, "botón de búsqueda SIMIT")
    btn.click()
    if debug:
        logger.debug("Clic en botón de búsqueda SIMIT enviado.")


def wait_for_results(
    page,
    debug: bool = True,
    timeout_ms: int | None = None,
) -> None:
    """Espera a que carguen los resultados de la consulta."""
    if timeout_ms is None:
        timeout_ms = get_settings().simit_results_timeout_ms

    if debug:
        logger.debug("Esperando resultados de SIMIT…")

    result_selectors = [
        "#resumenEstadoCuenta",
        "#multaTable",
        "#acuerdoTable",
        "text=/No tienes comparendos ni multas/i",
        "text=/no posee a la fecha pendientes/i",
        "text=/Estado de cuenta/i",
    ]

    for selector in result_selectors:
        try:
            page.wait_for_selector(selector, timeout=timeout_ms)
            if debug:
                logger.debug("Resultado SIMIT detectado (%s).", selector)
            page.wait_for_timeout(1500)
            return
        except PWTimeoutError:
            continue

    if debug:
        logger.warning(
            "No se detectó selector de resultado SIMIT específico; "
            "capturando HTML de todas formas."
        )
    page.wait_for_timeout(2000)


def run_simit_flow(
    identificador: str,
    headless: bool | None = None,
    slow_mo: int | None = None,
    debug: bool | None = None,
) -> str:
    """
    Ejecuta el flujo completo de consulta en SIMIT.
    Retorna el HTML de la página de resultados.
    """
    settings = get_settings()
    if headless is None:
        headless = settings.browser_headless
    if slow_mo is None:
        slow_mo = settings.simit_slow_mo_ms
    if debug is None:
        debug = settings.debug

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()

        try:
            logger.info("Abriendo portal SIMIT…")
            page.goto(
                settings.simit_url,
                timeout=settings.navigation_timeout_ms,
            )

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=settings.simit_network_idle_timeout_ms,
                )
            except PWTimeoutError:
                pass

            page.wait_for_timeout(1000)
            dismiss_promo_modal(page, debug=debug)

            fill_search_input(page, identificador, debug=debug)
            click_search_button(page, debug=debug)
            wait_for_results(page, debug=debug)

            html = page.content()
            if debug:
                logger.debug("HTML SIMIT size: %s", len(html))
                logger.debug(
                    "contains resumenEstadoCuenta: %s",
                    "resumenEstadoCuenta" in html,
                )
                logger.debug("contains multaTable: %s", "multaTable" in html)

            logger.info("Consulta SIMIT completada (html_bytes=%s).", len(html))
            return html

        finally:
            try:
                browser.close()
            except Exception:
                pass
