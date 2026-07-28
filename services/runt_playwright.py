# services/runt_playwright.py
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
# Este módulo es el camino activo de automatización RUNT (vía controllers/services).
# Entry points de la app: app.py (consola) y app_gui.py (GUI).
# Requiere haber ejecutado antes:
#   pip install playwright
#   python -m playwright install chromium
#
# ------------------------------------------------------------
# IMPORTACIONES
# playwright.sync_api: automatizar y controlar navegadores web (biblioteca externa)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
# Buscar o validar patrones de texto (biblioteca estándar)
import re
# Manejar rutas y archivos fácilmente (estándar)
from pathlib import Path

from config.settings import get_settings


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
def select_tipo_documento(page, codigo: str, debug: bool = True):
    """
    Selecciona el tipo de documento en el mat-select de la página.
    La vista nos pasa un código corto (CC, CE, TI, PPT, etc.)
    y aquí lo mapeamos al texto visible real del mat-option.
    """
    import re

    # Mapa de códigos -> texto visible EXACTO en el combo
    mapa_tipos = {
        "CC": "Cédula Ciudadanía",
        "CD": "Carnet Diplomático",
        "CE": "Cédula de Extranjería",
        "PA": "Pasaporte",
        "TI": "Tarjeta de Identidad",
        "RC": "Registro Civil",
        "PPT": "Permiso por Protección Temporal",
    }

    codigo = codigo.upper().strip()
    visible = mapa_tipos.get(codigo)

    if visible is None:
        # Si nos pasan algo que no está en el mapa, usamos el valor tal cual
        visible = codigo

    # Regex tolerante a espacios extra
    patron = re.compile(r"\s*".join(map(re.escape, visible.split())), re.I)

    # 1) Localiza el mat-select
    select_candidates = [
        "mat-select[formcontrolname='tipoDocumento']",
        lambda p: p.get_by_role("combobox", name=re.compile(r"Tipo\s*de\s*Documento", re.I)),
        lambda p: p.get_by_label(re.compile(r"Tipo\s*de\s*Documento", re.I)),
    ]
    select_loc = pick_first_working_locator(page, select_candidates, "combo de 'Tipo de documento'")

    # 2) Abre el combo
    if debug:
        print(f"🖱️ Abriendo el combo de tipo de documento (código={codigo})…")
    select_loc.click()

    # 3) Espera el overlay
    try:
        page.wait_for_selector(".cdk-overlay-container .mat-select-panel", timeout=8000)
    except Exception:
        if debug:
            print("⚠ No apareció el panel del combo. Reintentando clic…")
        select_loc.click()
        page.wait_for_selector(".cdk-overlay-container .mat-select-panel", timeout=8000)

    if debug:
        print(f"📜 Buscando opción para código '{codigo}' → '{visible}'")

    # 4) Opciones dentro del overlay
    opciones_texto = page.locator(".cdk-overlay-container .mat-option-text")

    # 5) Click en la opción cuyo texto coincida
    try:
        opciones_texto.filter(has_text=patron).first.click(timeout=8000)
        if debug:
            print(f"✅ Opción '{visible}' seleccionada para código '{codigo}'.")
    except Exception as e:
        # Fallback por rol
        try:
            page.get_by_role("option", name=patron).first.click(timeout=8000)
            if debug:
                print(f"✅ Opción '{visible}' seleccionada (fallback role=option).")
        except Exception as e2:
            raise RuntimeError(
                f"No se pudo seleccionar el tipo de documento '{codigo}' ('{visible}'). "
                f"Revisa si el texto cambió en el HTML. Errores: {e} / {e2}"
            )



def fill_numero_documento(page, numero: str, debug: bool = True):
    """
    Llena el número de documento en el input correspondiente.
    Ajusta los selectores si la página cambia.
    """
    if debug:
        print("⌨️ Buscando campo de número de documento…")

    input_candidates = [
        # 1) Lo que vemos en el HTML real
        "input[formcontrolname='documento']",
        "input#mat-input-0",

        # 2) Alternativas por si cambian el id
        lambda p: p.get_by_label(re.compile(r"Nro\.\s*documento", re.I)),
        lambda p: p.get_by_placeholder(re.compile(r"Nro\.\s*documento", re.I)),

        # 3) Fallback genérico
        lambda p: p.get_by_role("textbox").nth(0),
        lambda p: p.get_by_role("textbox").nth(1),
    ]

    input_loc = pick_first_working_locator(page, input_candidates, "campo 'Número de documento'")
    input_loc.fill(numero)
    if debug:
        print(f"✅ Número de documento '{numero}' llenado.")


def dismiss_autocomplete_popup(page, debug: bool = True):
    """
    Intenta cerrar el popup rosado de 'Hemos mejorado Autocompletar'
    si está presente, para que no estorbe al captcha ni a otros elementos.

    Si no se encuentra nada, simplemente sigue sin lanzar error.
    """
    try:
        # Buscamos el texto principal del popup
        popup = page.get_by_text(re.compile(r"Hemos mejorado\s+Autocompletar", re.I))
        # Si no está visible, no hacemos nada
        popup.wait_for(state="visible", timeout=3000)

        if debug:
            print("🩷 Popup de 'Autocompletar' detectado. Intentando cerrarlo…")

        # Intentamos primero el botón de cerrar (la X)
        close_candidates = [
            lambda p: p.get_by_role("button", name=re.compile(r"cerrar|×|x", re.I)),
            ".swal2-close",
            # Como fallback, el botón "Quizás más tarde"
            lambda p: p.get_by_role("button", name=re.compile(r"quiz[aá]s m[aá]s tarde", re.I)),
        ]

        btn_close = None
        for cand in close_candidates:
            try:
                loc = cand(page) if callable(cand) else page.locator(cand)
                loc.wait_for(state="visible", timeout=1500)
                btn_close = loc
                break
            except Exception:
                continue

        if btn_close is not None:
            btn_close.click()
            if debug:
                print("✅ Popup de 'Autocompletar' cerrado.")
            page.wait_for_timeout(300)  # pequeño respiro
        else:
            if debug:
                print("ℹ No se encontró botón claro para cerrar el popup, se continúa.")

    except PWTimeoutError:
        # No apareció el popup; todo bien
        if debug:
            print("ℹ No se detectó popup de 'Autocompletar'.")
    except Exception as e:
        if debug:
            print(f"⚠ Error intentando cerrar popup de autocompletar: {e}")


def try_capture_and_solve_captcha(
    page,
    resolver_captcha=None,
    debug: bool = True,
    timeout_ms: int | None = None,
):
    """
    - Busca la imagen del CAPTCHA.
    - La captura en bytes (screenshot).
    - Si se proporciona resolver_captcha(image_bytes) -> texto,
      llama a esa función (GUI o consola).
    - Si no se pasa resolver_captcha, por compatibilidad guarda
      captcha.png y pide input().
    """
    if timeout_ms is None:
        timeout_ms = get_settings().runt_captcha_timeout_ms

    if debug:
        print("🧩 Buscando imagen de CAPTCHA…")

    # Selectores ajustados a la estructura que vimos
    captcha_img_candidates = [
        "div.divCaptcha img",
        "img[alt*='captcha' i]",
        "img[title*='captcha' i]",
        "img[src^='data:image'][src*='captcha']",
        lambda p: p.get_by_role("img", name=re.compile(r"captcha", re.I)),
    ]

    captcha_img = pick_first_working_locator(page, captcha_img_candidates, "imagen de CAPTCHA")

    # Intentamos capturar el screenshot con timeout controlado
    try:
        image_bytes = captcha_img.screenshot(timeout=timeout_ms)  # bytes en memoria
    except PWTimeoutError:
        # Aquí puedes decidir reintentar o fallar duro. Por ahora, fallamos con mensaje claro.
        raise RuntimeError(
            "No se pudo capturar la imagen del CAPTCHA a tiempo. "
            "La página puede estar lenta o el componente cambió."
        )

    # -------- Resolver el texto del captcha --------
    if resolver_captcha is not None:
        captcha_text = resolver_captcha(image_bytes)
    else:
        # Fallback consola: guardar PNG y pedir input aquí mismo
        tmp_path = Path("captcha.png").absolute()
        tmp_path.write_bytes(image_bytes)
        if debug:
            print(f"🖼 CAPTCHA guardado en: {tmp_path}")
        captcha_text = input("👉 Texto del CAPTCHA: ").strip()

    if debug:
        print(f"🔐 CAPTCHA ingresado: '{captcha_text}'")

    # -------- Escribir el captcha en el input correspondiente --------
    captcha_input_candidates = [
        "input[formcontrolname='captcha']",
        "input[name='captcha']",
        lambda p: p.get_by_placeholder(re.compile(r"Digite.*caracteres", re.I)),
        lambda p: p.get_by_label(re.compile(r"captcha", re.I)),
    ]
    captcha_input = pick_first_working_locator(page, captcha_input_candidates, "campo de texto del CAPTCHA")
    captcha_input.fill(captcha_text)


def check_and_handle_captcha_error(page, debug: bool = True) -> bool:
    """
    Detecta el popup de SweetAlert2 con el mensaje 'El captcha no es valido.'
    y, si existe, hace clic en el botón 'Aceptar'.
    Devuelve True si encontró y manejó el error, False si no había error de captcha.
    """

    # Popup principal de SweetAlert2
    popup = page.locator("div.swal2-popup")
    try:
        popup.wait_for(state="visible", timeout=1500)
    except PWTimeoutError:
        # No hay popup visible → no hay error de captcha
        return False
    except Exception:
        return False

    # Leer el texto del popup (título + contenido)
    try:
        popup_text = popup.inner_text()
    except Exception:
        popup_text = ""

    if debug:
        print(f"🪧 Texto del popup SweetAlert2: {popup_text!r}")

    # ¿Es el popup específico del captcha?
    if not re.search(r"El\s+captcha\s+no\s+es\s+v[aá]lido", popup_text, re.I):
        # Es otro mensaje cualquiera, no de captcha
        return False

    if debug:
        print("❌ CAPTCHA incorrecto: popup 'El captcha no es valido.' detectado.")

    # Intentar hacer clic en el botón Aceptar
    try:
        # Según tu HTML: <button class="swal2-confirm swal2-styled">Aceptar</button>
        popup.locator("button.swal2-confirm").click()
        if debug:
            print("🧹 Botón 'Aceptar' (swal2-confirm) clickeado.")
    except Exception:
        # Fallback: buscar cualquier botón con texto Aceptar
        try:
            page.get_by_role("button", name=re.compile(r"Aceptar", re.I)).first.click()
            if debug:
                print("🧹 Botón 'Aceptar' clickeado (fallback get_by_role).")
        except Exception:
            if debug:
                print("⚠ No se pudo hacer clic automáticamente en 'Aceptar'.")

    # Dejar que se cierre el popup y se regenere el captcha
    page.wait_for_timeout(800)
    return True

def check_and_handle_person_not_found(page, debug: bool = True) -> bool:
    """
    Detecta el popup de SweetAlert2 con el mensaje
    'No se ha encontrado la persona en estado ACTIVA o SIN REGISTRO'
    y, si existe, hace clic en 'Aceptar'.

    Devuelve True si encontró y manejó ese caso (documento inexistente / sin registro),
    False si no apareció ese mensaje.
    """

    # Popup principal de SweetAlert2
    popup = page.locator("div.swal2-popup")
    try:
        popup.wait_for(state="visible", timeout=1500)
    except PWTimeoutError:
        # No hay popup visible → no hay error de "persona no encontrada"
        return False
    except Exception:
        return False

    # Leer el texto del popup (título + contenido)
    try:
        popup_text = popup.inner_text()
    except Exception:
        popup_text = ""

    if debug:
        print(f"🪧 Texto del popup SweetAlert2: {popup_text!r}")

    # ¿Es el popup específico de persona no encontrada?
    import re
    patron_no_encontrada = re.compile(
        r"No\s+se\s+ha\s+encontrado\s+la\s+persona\s+en\s+estado\s+ACTIVA\s+o\s+SIN\s+REGISTRO",
        re.I,
    )

    if not patron_no_encontrada.search(popup_text or ""):
        # Es otro mensaje diferente → no lo tratamos aquí
        return False

    if debug:
        print("ℹ️ RUNT indica: 'No se ha encontrado la persona en estado ACTIVA o SIN REGISTRO'.")

    # Intentar hacer clic en el botón Aceptar
    try:
        popup.locator("button.swal2-confirm").click()
        if debug:
            print("🧹 Botón 'Aceptar' (swal2-confirm) clickeado para cerrar el popup de 'sin registro'.")
    except Exception:
        try:
            page.get_by_role("button", name=re.compile(r"Aceptar", re.I)).first.click()
            if debug:
                print("🧹 Botón 'Aceptar' clickeado (fallback get_by_role).")
        except Exception:
            if debug:
                print("⚠ No se pudo hacer clic automáticamente en 'Aceptar' (sin registro).")

    page.wait_for_timeout(800)
    return True



def click_consultar(page, debug: bool = True):
    """
    Hace clic en el botón 'Consultar' o similar para enviar el formulario.
    """
    if debug:
        print("🔘 Buscando botón 'Consultar'…")

    button_candidates = [
        "button[type='submit']",
        "button[color='primary']",
        lambda p: p.get_by_role("button", name=re.compile(r"consultar", re.I)),
    ]

    btn = pick_first_working_locator(page, button_candidates, "botón 'Consultar'")
    btn.click()
    if debug:
        print("✅ Clic en botón 'Consultar' enviado.")



def expand_all_panels_and_wait_data(page, debug: bool = False, settle_ms: int = 800) -> None:
    """
    Expande todos los mat-expansion-panel del acordeón y espera a que Angular renderice
    el contenido (tablas/labels/valores) dentro de cada panel.

    Esto es clave porque muchas secciones NO renderizan filas/valores hasta que el panel
    se expande (lazy rendering).
    """
    def log(msg: str) -> None:
        if debug:
            print(msg)

    # Asegura que existan panels en DOM (aunque sea sin datos)
    try:
        page.wait_for_selector("mat-expansion-panel", timeout=8000)
    except Exception:
        log("⚠ No se encontraron mat-expansion-panel para expandir.")
        return

    panels = page.locator("mat-expansion-panel")
    total = panels.count()
    log(f"🔎 Panels encontrados: {total}")

    for i in range(total):
        panel = panels.nth(i)
        header = panel.locator("mat-expansion-panel-header")

        # Título del panel (solo para debug)
        title = ""
        try:
            title = header.locator(".panel-title-text").inner_text(timeout=500)
            title = title.strip()
        except Exception:
            pass

        # ¿Está expandido?
        expanded = None
        try:
            expanded = header.get_attribute("aria-expanded")
        except Exception:
            expanded = None

        if expanded != "true":
            try:
                log(f"➡ Expandiendo panel #{i+1}/{total} {('— ' + title) if title else ''}")
                header.scroll_into_view_if_needed()
                header.click()
            except Exception as e:
                log(f"⚠ No se pudo expandir panel #{i+1}: {e}")
                continue

        # Espera a que el contenido del panel exista (region body)
        # Cada panel suele tener un div con role="region" mat-expansion-panel-content
        try:
            panel.locator(".mat-expansion-panel-content").wait_for(state="visible", timeout=3000)
        except Exception:
            # Algunos quedan visibles pero sin height; aún así, damos tiempo a render.
            pass

        # Espera un poco para que Angular pinte el contenido real.
        # Esto ayuda para: tablas mat-table, forms con <b>, etc.
        page.wait_for_timeout(250)

        # Espera a que Angular renderice filas reales, valores o mensaje "Sin información"
        try:
            handle = panel.element_handle()
            if handle:
                page.wait_for_function(
                    """(panel) => {
                        // 1) Tablas con filas
                        const hasRows = panel.querySelectorAll('tbody tr').length > 0;

                        // 2) Valores en <b> (formularios tipo Multas / Validación)
                        const hasBoldValues = Array.from(panel.querySelectorAll('b'))
                            .some(b => b.innerText && b.innerText.trim().length > 0);

                        // 3) Mensajes explícitos de vacío
                        const txt = panel.innerText.toLowerCase();
                        const hasEmptyMsg =
                            txt.includes('sin información') ||
                            txt.includes('no se encontró información');

                        return hasRows || hasBoldValues || hasEmptyMsg;
                    }""",
                    arg=handle,
                    timeout=6000
                )
        except Exception:
            pass



    # Tiempo final para que todo “asiente”
    page.wait_for_timeout(settle_ms)
    log("✅ Todos los panels fueron procesados (expand/settle).")



# ------------------------------------------------------------
# FUNCIÓN PRINCIPAL: flujo completo del RUNT
# ------------------------------------------------------------
def run_runt_flow(
    tipo: str,
    numero: str,
    headless: bool | None = None,
    slow_mo: int | None = None,
    resolver_captcha=None,
    debug: bool | None = None,
    hold_after: bool = False,
) -> str | None:
    """
    Ejecuta todo el flujo:
      - Abre el navegador
      - Navega al RUNT
      - Llena tipo y número de documento
      - Intenta cerrar el popup de Autocompletar (si aparece)
      - Pide resolver CAPTCHA en un bucle hasta que sea correcto
      - Envía formulario
      - Detecta si no hay registro
      - Si hay resultados, retorna el HTML completo de la página
    Retorna:
      - str: HTML completo cuando la consulta fue exitosa
      - None: cuando la persona está SIN REGISTRO / no activa
    """
    settings = get_settings()
    if headless is None:
        headless = settings.browser_headless
    if slow_mo is None:
        slow_mo = settings.runt_slow_mo_ms
    if debug is None:
        debug = settings.debug

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()

        try:
            if debug:
                print("🌐 Abriendo portal del RUNT…")
            page.goto(
                settings.runt_url,
                timeout=settings.navigation_timeout_ms,
            )

            # Angular a veces no llega a networkidle; no lo tratamos como fatal
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=settings.runt_network_idle_timeout_ms,
                )
            except PWTimeoutError:
                pass

            # -----------------------------
            # Llenar tipo + número
            # -----------------------------
            if debug:
                print(f"📝 Seleccionando tipo='{tipo}' y llenando número='{numero}'…")
            select_tipo_documento(page, tipo, debug=debug)
            fill_numero_documento(page, numero, debug=debug)

            # Intentar cerrar popup “Hemos mejorado Autocompletar”
            dismiss_autocomplete_popup(page, debug=debug)

            # ----------------------------------------------------
            # BUCLE DE CAPTCHA: seguimos hasta que NO haya error
            # ----------------------------------------------------
            intentos = 0
            LIMITE_SEGURIDAD = 20  # por si algo sale mal y no detectamos bien el error

            while True:
                intentos += 1
                if debug:
                    print(f"🔁 Intento de CAPTCHA #{intentos}…")

                if intentos > LIMITE_SEGURIDAD:
                    raise RuntimeError(
                        "Se superó el límite de intentos de CAPTCHA (seguridad). "
                        "Revisa si cambió el mensaje de error en el sitio."
                    )

                # 1) Capturar y resolver captcha actual
                try_capture_and_solve_captcha(
                    page,
                    resolver_captcha=resolver_captcha,
                    debug=debug,
                )

                # 2) Enviar consulta
                click_consultar(page, debug=debug)

                # 3) Espera breve para que responda el front
                page.wait_for_timeout(1500)

                # 4) ¿Captcha inválido?
                if check_and_handle_captcha_error(page, debug=debug):
                    # Se generará uno nuevo; volvemos a intentar
                    continue

                if debug:
                    print("✅ No se detectó error de CAPTCHA; continuando flujo.")
                break

            # ----------------------------------------------------
            # Verificar "persona no encontrada / sin registro"
            # ----------------------------------------------------
            if check_and_handle_person_not_found(page, debug=debug):
                if debug:
                    print("⚠ La persona no tiene registro ACTIVO en RUNT (o SIN REGISTRO).")
                if hold_after and debug:
                    input("⏸ Documento sin registro. Presiona ENTER para cerrar el navegador…")
                return None  # ✅ coherente con -> str | None

            # ----------------------------------------------------
            # Capturar HTML de resultados
            # ----------------------------------------------------
            if debug:
                print("⏳ Consulta enviada satisfactoriamente. Capturando resultados…")

            # Esperamos un elemento típico de resultados (puede cambiar, pero sirve como ancla)
            try:
                page.wait_for_selector("mat-expansion-panel", timeout=15000)
            except PWTimeoutError:
                # No lo tratamos como fatal: igual intentamos capturar lo que haya
                if debug:
                    print("⚠ No apareció 'mat-expansion-panel' a tiempo. Capturando HTML de todas formas…")
            
    
            expand_all_panels_and_wait_data(page, debug=debug)
            page.wait_for_timeout(800)

            html = page.content()

            if debug:
                print("🧪 HTML size:", len(html))
                print("🧪 contains mat-expansion-panel:", "mat-expansion-panel" in html)
                print("🧪 contains LICENCIAS keyword:", "Licencias de conducción" in html or "LICENCIA" in html.upper())
                print("🧪 contains tbody rows:", "<tbody" in html and "<tr" in html)


            if hold_after and debug:
                input(
                    "⏸ Verifica que los resultados estén cargados.\n"
                    "   Presiona ENTER cuando quieras cerrar el navegador…"
                )

            return html

        finally:
            # Asegura cierre incluso si ocurre error
            try:
                browser.close()
            except Exception:
                pass
