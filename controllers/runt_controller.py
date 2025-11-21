# controllers/runt_controller.py

from typing import Callable, Optional
from models.runt_models import ConsultaRuntParams, ResultadoRunt
from services.runt_playwright import run_runt_flow

# Tipo para la función que resuelve el captcha
ResolverCaptcha = Callable[[bytes], str]

class RuntController:
    def __init__(self):
        # Aquí luego podremos inyectar repositorios de BD, etc.
        pass

    def consultar_ciudadano(
        self,
        params: ConsultaRuntParams,
        resolver_captcha: Optional[ResolverCaptcha] = None,
        debug: bool = True,
    ) -> ResultadoRunt:
        """
        Orquesta la consulta: recibe params de la vista, llama al servicio,
        y devuelve un modelo ResultadoRunt.
        """
        # Ejecutamos el flujo Playwright
        ok = run_runt_flow(
            tipo=params.tipo_documento,
            numero=params.numero_documento,
            headless=False,
            slow_mo=300,
            resolver_captcha=resolver_captcha,
            debug=debug,
            hold_after=True,  # 👈 mantenemos el navegador abierto hasta que demos ENTER
        )

        if not ok:
            if debug:
                print("⚠ Resultado: documento sin registro o persona no activa en RUNT.")
            # Luego puedes reflejar esto en el modelo; por ahora devolvemos vacío.
            return ResultadoRunt(raw_html=None)

        # Por ahora devolvemos un resultado "vacío".
        # Luego aquí metemos los datos scrapeados.
        return ResultadoRunt()
