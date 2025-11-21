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

        

def try_capture_and_solve_captcha(page, resolver_captcha=None, debug: bool = True):
    """
    - Busca la imagen del CAPTCHA.
    - La captura en bytes (screenshot).
    - Si se proporciona resolver_captcha(image_bytes) -> texto,
      llama a esa función (GUI o consola).
    - Si no se pasa resolver_captcha, por compatibilidad guarda
      captcha.png y pide input().
    """
    import re

    # Darle un pequeño tiempo a Angular para que pinte el captcha
    page.wait_for_timeout(1500)

    if debug:
        print("🧩 Buscando imagen de CAPTCHA…")

    # Selector basado en el HTML real:
    # <img id="src" class="img-fluid" src="data:image/png;base64,...">
    def img_after_text(p):
        # Primer <img> que aparece después del texto del captcha
        return p.get_by_text(
            re.compile(r"Digite los caracteres presentados a continuación", re.I)
        ).locator("xpath=following::img[1]")

    captcha_img_candidates = [
        # A) Selectores específicos del captcha actual
        "img#src",                     # id="src"
        "img.img-fluid",               # por si cambian el id
        "img[src^='data:image']",      # src embebido en base64

        # B) Basado en el texto que acompaña al captcha
        img_after_text,

        # C) Fallback bruto: último <img> en la página
        lambda p: p.locator("xpath=(//img)[last()]"),
    ]

    try:
        captcha_img = pick_first_working_locator(page, captcha_img_candidates, "imagen de CAPTCHA")
    except RuntimeError:
        if debug:
            print("⚠ No se encontró la imagen del CAPTCHA con los selectores previstos.")
            # Mostrar info de las imágenes para depurar si algún día cambia el HTML
            imgs = page.locator("img")
            count = imgs.count()
            print(f"   Hay {count} etiquetas <img> en la página:")
            for i in range(min(count, 10)):
                try:
                    src = imgs.nth(i).get_attribute("src")
                    alt = imgs.nth(i).get_attribute("alt")
                    title = imgs.nth(i).get_attribute("title")
                    print(f"   [{i}] src={src!r}, alt={alt!r}, title={title!r}")
                except Exception:
                    pass
        raise

    # Screenshot en memoria
    image_bytes = captcha_img.screenshot()

    # Pedir al usuario que resuelva el captcha
    if resolver_captcha is not None:
        captcha_text = resolver_captcha(image_bytes)
    else:
        tmp_path = Path("captcha.png").absolute()
        tmp_path.write_bytes(image_bytes)
        if debug:
            print(f"🖼 CAPTCHA guardado en: {tmp_path}")
        captcha_text = input("👉 Texto del CAPTCHA: ").strip()

    if debug:
        print(f"🔐 CAPTCHA ingresado: '{captcha_text}'")

    # Campo donde se escribe el texto del captcha
    captcha_input_candidates = [
        "input[formcontrolname='captcha']",
        "input[name='captcha']",
        lambda p: p.get_by_placeholder(re.compile(r"Ingrese.*captcha", re.I)),
        lambda p: p.get_by_label(re.compile(r"Captcha", re.I)),
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
    except TimeoutError:
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
    except TimeoutError:
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



# ------------------------------------------------------------
# FUNCIÓN PRINCIPAL: flujo completo del RUNT
# ------------------------------------------------------------
def run_runt_flow(
    tipo: str,
    numero: str,
    headless: bool = False,
    slow_mo: int = 300,
    resolver_captcha=None,
    debug: bool = True,
    hold_after: bool = False,
):
    """
    Ejecuta todo el flujo:
      - Abre el navegador
      - Navega al RUNT
      - Llena tipo y número de documento
      - Pide resolver CAPTCHA en un bucle hasta que sea correcto
      - Envía formulario
      - (Más adelante) lee el panel de resultados
    """
    import re

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()

        if debug:
            print("🌐 Abriendo portal del RUNT…")
        page.goto(RUNT_URL, timeout=60000)

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeoutError:
            pass

        if debug:
            print(f"📝 Seleccionando tipo='{tipo}' y llenando número='{numero}'…")
        select_tipo_documento(page, tipo, debug=debug)
        fill_numero_documento(page, numero, debug=debug)

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
                browser.close()
                raise RuntimeError(
                    "Se superó el límite de intentos de CAPTCHA (seguridad). "
                    "Revisa si cambió el mensaje de error en el sitio."
                )

            # 1) Capturamos y resolvemos el captcha actual
            try_capture_and_solve_captcha(page, resolver_captcha=resolver_captcha, debug=debug)

            # 2) Enviamos la consulta
            click_consultar(page, debug=debug)

            # 3) Esperamos un poco a que el front responda
            page.wait_for_timeout(1500)

            # 4) ¿Apareció el popup 'El captcha no es valido.'?
            if check_and_handle_captcha_error(page, debug=debug):
                # Ya clickeamos 'Aceptar'; se generará un nuevo captcha.
                # Volvemos al inicio del while: te pedirá uno nuevo.
                continue

            # Si llegamos aquí, asumimos que NO hubo error de captcha
            if debug:
                print("✅ No se detectó error de CAPTCHA; continuando flujo.")
            break

        # ----------------------------------------------------
        # Después de un CAPTCHA válido verificamos si el RUNT
        # respondió "persona no encontrada / sin registro"
        # ----------------------------------------------------
        if check_and_handle_person_not_found(page, debug=debug):
            # No hay resultados para ese documento
            if debug:
                print("⚠ La persona no tiene registro ACTIVO en RUNT (o SIN REGISTRO).")
            # Opcional: mantener la ventana abierta si quieres ver la pantalla
            if hold_after and debug:
                input("⏸ Documento sin registro. Presiona ENTER para cerrar el navegador…")
            browser.close()
            return False  # <- el flujo terminó, pero sin datos

        # ----------------------------------------------------
        # Aquí ya asumimos que la consulta se realizó bien
        # (pendiente: parseo del panel de resultados)
        # ----------------------------------------------------
        if debug:
            print("⏳ Consulta enviada satisfactoriamente. (Pendiente: parseo de resultados)")

        if hold_after:
            if debug:
                input("⏸ Deja que carguen los resultados.\n   Presiona ENTER cuando quieras cerrar el navegador…")

        browser.close()
        return True
