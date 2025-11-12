# ------------------------------------------------------------
# FUNCIÓN 3: rellenar número de documento
# ------------------------------------------------------------
def fill_numero_documento(page, numero: str, debug: bool = True):
    """
    Rellena el campo del número de documento.
    En Angular Material, muchas veces el <label> no asocia aria al <input>,
    así que buscamos el mat-form-field por su texto y luego el input dentro.
    """
    import re

    candidates = [
        # Angular típico por formcontrolname
        "input[formcontrolname='numeroDocumento']",
        # A veces usan mat-input-* como id progresivo
        "input[id^='mat-input-']",
        # Buscar el mat-form-field que contiene el texto 'Número de Documento' y luego el input
        "mat-form-field:has-text('Número de Documento') input",
        # Variante tolerante a mayúsculas/acentos/nbsp
        lambda p: p.locator("mat-form-field", has_text=re.compile(r"N(ú|u)mero\s*de\s*Documento", re.I)).locator("input"),
        # Si usan placeholder
        "input[placeholder*='ocumento' i]",
        # Si exponen nombre accesible
        lambda p: p.get_by_role("textbox", name=re.compile(r"(n(ú|u)mero.*documento|documento)", re.I)),
    ]

    input_loc = pick_first_working_locator(page, candidates, "input de 'Número de documento'")

    if debug:
        print(f"⌨️ Escribiendo número '{numero}'…")
    input_loc.click()
    input_loc.fill(numero)



# ------------------------------------------------------------
# FUNCIÓN 4: hacer clic en el botón "Consultar"
# ------------------------------------------------------------
def click_consultar(page):
    """
    Localiza y hace clic en el botón “Consultar”.
    """
    btn_candidates = [
        lambda p: p.get_by_role("button", name=re.compile(r"consultar", re.I)),
        "button#btnConsultar",
        "button.btn-primary",
        "button[type='submit']",
    ]
    btn = pick_first_working_locator(page, btn_candidates, "botón 'Consultar'")
    btn.click()


# ------------------------------------------------------------
# FUNCIÓN 5: detectar y permitir resolver el CAPTCHA
# ------------------------------------------------------------
def try_capture_and_solve_captcha(page, pausa=True, debug=True):
    """
    Intenta localizar el CAPTCHA (si existe) y permite que el usuario lo resuelva manualmente.
    """
    captcha_img_candidates = [
        "img[alt*='captcha' i]",
        "img[src*='captcha' i]",
        "canvas[aria-label*='captcha' i]",
        lambda p: p.get_by_role("img", name=re.compile("captcha", re.I)),
    ]

    try:
        captcha_img = pick_first_working_locator(page, captcha_img_candidates, "imagen/caja de CAPTCHA")
    except RuntimeError:
        if debug:
            print("ℹ No se detectó CAPTCHA visible.")
        return

    # Si se encuentra una imagen de CAPTCHA, intentamos guardarla
    out = Path("captcha.png")
    try:
        captcha_img.screenshot(path=str(out))
        if debug:
            print(f"🖼  Captcha capturado en {out.resolve()}")
    except Exception:
        if debug:
            print("⚠ No se pudo capturar la imagen del captcha (puede ser un canvas o protegido).")

    if not pausa:
        return

    # Buscamos el input donde se escribe el captcha
    captcha_input_candidates = [
        "input[formcontrolname*='captcha' i]",
        "input#captcha",
        "input[name*='captcha' i]",
        lambda p: p.get_by_label(re.compile(r"captcha", re.I)),
        lambda p: p.get_by_role("textbox", name=re.compile(r"captcha", re.I)),
    ]
    try:
        captcha_input = pick_first_working_locator(page, captcha_input_candidates, "campo del CAPTCHA")
    except RuntimeError:
        print("⚠ No se encontró el campo del CAPTCHA. Escríbelo directamente en la página.")
        input("➡ Presiona ENTER cuando hayas resuelto el CAPTCHA manualmente…")
        return

    # Pedimos al usuario ingresar el texto del captcha
    solucion = input("🔐 Escribe el texto del CAPTCHA (visible en la página o captcha.png): ").strip()
    if solucion:
        captcha_input.fill(solucion)