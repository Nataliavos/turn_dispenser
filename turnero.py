# turnero.py
# ------------------------------------------------------------
# Automatización del portal público del RUNT (https://portalpublico.runt.gov.co)
# Objetivo:
#   - Abrir el navegador.
#   - Navegar a la página de consulta por documento.
#   - Seleccionar tipo de documento.
#   - Ingresar número de documento.
#   - Permitir resolver el CAPTCHA manualmente.
#   - Enviar la consulta.
#   - Detectar si se cargaron los resultados.
#
# Este flujo usa Playwright, una librería moderna de automatización de navegadores.
# Requiere haber ejecutado antes:
#   pip install playwright
#   python -m playwright install
#
# Uso:
#   python turnero.py --tipo CC --numero 123456789 --hold
#
# ------------------------------------------------------------
# IMPORTACIONES
# playwright.sync_api: automatizar y controlar navegadores web (biblioteca externa)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
# Buscar o validar patrones de texto (biblioteca estándar)
import re
# Leer argumentos de línea de comandos (estándar)
import argparse
# Manejar rutas y archivos fácilmente (estándar)
from pathlib import Path


# URL principal del módulo de consulta ciudadana del RUNT
RUNT_URL = "https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento/consulta/consulta-ciudadano-documento"


# ------------------------------------------------------------
# FUNCIÓN AUXILIAR 1: buscar el primer selector que funcione
# ------------------------------------------------------------
def pick_first_working_locator(page, locator_candidates, description="elemento"):
    """
    Intenta encontrar un elemento en la página usando una lista de posibles selectores.
    Retorna el primer selector que encuentre visible.
    Esto se usa porque las páginas Angular (como la del RUNT) pueden tener nombres dinámicos.
    """
    for css_or_getter in locator_candidates:
        try:
            # css_or_getter puede ser:
            # 1) un string CSS ("input[name='numeroDocumento']")
            # 2) una función que devuelve un locator (lambda p: p.get_by_label(...))
            loc = css_or_getter(page) if callable(css_or_getter) else page.locator(css_or_getter)
            loc.wait_for(state="visible", timeout=5000)
            return loc
        except PWTimeoutError:
            continue
        except Exception:
            continue
    raise RuntimeError(f"No se encontró {description}. Ajusta los selectores según el HTML real.")


# ------------------------------------------------------------
# FUNCIÓN 2: seleccionar tipo de documento
# ------------------------------------------------------------
def select_tipo_documento(page, valor_visible_o_value: str, debug: bool = True):
    """
    Selecciona el tipo de documento en <mat-select formcontrolname="tipoDocumento">.
    Abre el combo, espera el panel overlay y hace clic en la opción cuyo texto coincida.
    """
    import re

    # 1) Localiza el mat-select por formcontrolname, o por rol/label como fallback
    select_candidates = [
        "mat-select[formcontrolname='tipoDocumento']",
        lambda p: p.get_by_role("combobox", name=re.compile(r"Tipo\s*de\s*Documento", re.I)),
        lambda p: p.get_by_label(re.compile(r"Tipo\s*de\s*Documento", re.I)),
    ]
    select_loc = pick_first_working_locator(page, select_candidates, "combo de 'Tipo de documento'")

    # 2) Abre el combo
    if debug:
        print("🖱️ Abriendo el combo de tipo de documento…")
    select_loc.click()

    # 3) Espera el overlay del panel de Angular Material
    #    (el contenedor aparece fuera del flujo de la página en .cdk-overlay-container)
    try:
        page.wait_for_selector(".cdk-overlay-container .mat-select-panel", timeout=8000)
    except Exception:
        if debug:
            print("⚠ No apareció el panel del combo. Reintentando clic…")
        select_loc.click()
        page.wait_for_selector(".cdk-overlay-container .mat-select-panel", timeout=8000)

    # 4) Busca la opción por su texto dentro de .mat-option-text
    if debug:
        print(f"📜 Buscando opción '{valor_visible_o_value}'…")

    # Tolerante a espacios duros (&nbsp) y variaciones
    texto_regex = re.compile(valor_visible_o_value.replace(" ", r"\s+"), re.I)

    # Localiza todas las opciones visibles y filtra por texto
    opciones_texto = page.locator(".cdk-overlay-container .mat-option-text")
    count = opciones_texto.count()

    # Si quieres ver qué opciones hay (útil para depurar):
    # for i in range(count):
    #     print("→", opciones_texto.nth(i).inner_text().strip())

    # Filtra por el texto esperado y hace clic
    try:
        opciones_texto.filter(has_text=texto_regex).first.click(timeout=8000)
        if debug:
            print(f"✅ Opción '{valor_visible_o_value}' seleccionada.")
    except Exception as e:
        # Fallback por rol (algunas versiones sí exponen role="option")
        try:
            page.get_by_role("option", name=texto_regex).first.click(timeout=8000)
            if debug:
                print(f"✅ Opción '{valor_visible_o_value}' seleccionada (fallback role=option).")
        except Exception as e2:
            raise RuntimeError(
                f"No se pudo seleccionar '{valor_visible_o_value}'. "
                f"Revisa el texto exacto del mat-option (acentos/espacios). "
                f"Errores: {e} / {e2}"
            )



# ------------------------------------------------------------
# FUNCIÓN PRINCIPAL: flujo completo del RUNT
# ------------------------------------------------------------
def run_runt_flow(tipo: str, numero: str, headless=False, slow_mo=300, hold_after=False, debug=True):
    """
    Ejecuta todo el flujo:
      - Abre el navegador
      - Navega al RUNT
      - Llena tipo y número de documento
      - Pide resolver CAPTCHA manualmente
      - Envía formulario
      - Detecta panel de resultados
    """
    with sync_playwright() as p:
        # Abre navegador Chromium
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()

        if debug:
            print("🌐 Abriendo portal del RUNT…")
        page.goto(RUNT_URL, timeout=60000)

        # Esperamos un momento a que se estabilice la carga (Angular tarda en renderizar)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeoutError:
            pass

        # Llenamos el formulario
        if debug:
            print(f"📝 Seleccionando tipo='{tipo}' y llenando número='{numero}'…")
        select_tipo_documento(page, tipo, debug=debug)
        fill_numero_documento(page, numero)

        # Intentamos procesar CAPTCHA manualmente
        try_capture_and_solve_captcha(page, pausa=True, debug=debug)

        # Enviamos la consulta
        if debug:
            print("🔎 Enviando la consulta…")
        click_consultar(page)

        # Intentamos detectar resultados o panel de información
        result_candidates = [
            lambda p: p.get_by_text(re.compile(r"resultado|informaci[oó]n|nombre|estado", re.I)),
            ".resultado, .panel-resultados, .table, .mat-table",
        ]
        try:
            pick_first_working_locator(page, result_candidates, "panel de resultados")
            if debug:
                print("✅ Parece que se cargaron resultados.")
        except RuntimeError:
            if debug:
                print("ℹ No se identificó un panel de resultados (verifica visualmente).")

        if hold_after:
            input("⏸  Presiona ENTER para cerrar el navegador…")

        browser.close()


# ------------------------------------------------------------
# BLOQUE MAIN (ejecución desde consola)
# ------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Automatiza la consulta en RUNT (captcha manual).")
    parser.add_argument("--tipo", required=True, help="Tipo de documento (CC, CE, NIT, etc.)")
    parser.add_argument("--numero", required=True, help="Número de documento")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin mostrar ventana del navegador.")
    parser.add_argument("--slow_mo", type=int, default=300, help="Retraso entre acciones (milisegundos).")
    parser.add_argument("--hold", action="store_true", help="Mantener ventana abierta al finalizar.")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Desactivar mensajes de depuración.")
    args = parser.parse_args()

    run_runt_flow(
        tipo=args.tipo,
        numero=args.numero,
        headless=args.headless,
        slow_mo=args.slow_mo,
        hold_after=args.hold,
        debug=args.debug,
    )


# ------------------------------------------------------------
# Punto de entrada del script
# ------------------------------------------------------------
if __name__ == "__main__":
    main()
