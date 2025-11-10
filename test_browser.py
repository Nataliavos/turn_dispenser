# test_browser.py
# ----------------------------------------
# Este script verifica que Playwright esté funcionando correctamente.
# Abre una ventana de navegador Chromium y navega a la página del RUNT.

from playwright.sync_api import sync_playwright

# Bloque principal: ejecuta Playwright de forma sincronizada
with sync_playwright() as p:
    # Lanzamos el navegador Chromium (puedes cambiar a firefox o webkit)
    browser = p.chromium.launch(headless=False, slow_mo=1000)  # headless=False -> muestra la ventana / True no la muestra

    # Abrimos una nueva pestaña
    page = browser.new_page()

    # Navegamos a la página del RUNT
    page.goto("https://portalpublico.runt.gov.co/#/consulta-ciudadano-documento/consulta/consulta-ciudadano-documento")

    # Imprimimos el título de la página para confirmar que cargó
    print("Título de la página:", page.title())

    # Esperamos unos segundos para ver la ventana
    page.wait_for_timeout(5000)  # 5000 ms = 5 segundos

    # Cerramos el navegador
    #browser.close() # comentamos esta línea para que el navegador permanezca abierto

print("✅ Prueba completada correctamente.")
