# test_browser.py
# ----------------------------------------
# Este script verifica que Playwright esté funcionando correctamente.
# Abre una ventana de navegador Chromium y navega a la página del RUNT.

from playwright.sync_api import sync_playwright

# Bloque principal: ejecuta Playwright de forma sincronizada
with sync_playwright() as p:
    # Lanzamos el navegador Chromium
    # headless=False → muestra el navegador (modo visible)
    # slow_mo=1000 → añade 1 segundo de pausa entre acciones (para observar)
    browser = p.chromium.launch(headless=False, slow_mo=1000)  # headless=False -> muestra la ventana / True no la muestra

    # Creamos un nuevo contexto (como una sesión o perfil temporal del navegador)
    context = browser.new_context()

    # Abrimos una nueva pestaña dentro de ese contexto
    page = context.new_page()

    # Navegamos a la página del RUNT - consulta por documento
    page.goto("https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento/consulta/consulta-ciudadano-documento")

    print("✅ Navegador abierto. Puedes inspeccionar manualmente.")

    # Pausa el script hasta que presiones ENTER en la terminal
    # Esto permite mantener el navegador abierto el tiempo que necesites
    input("Presiona ENTER para cerrar el navegador...")

    # Cierra completamente el navegador y la sesión de Playwright
    browser.close()
