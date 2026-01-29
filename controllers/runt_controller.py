from typing import Callable, Optional
from models.runt_models import ConsultaRuntParams, ResultadoRunt
from services.runt_playwright import run_runt_flow
from services.runt_parser import parse_runt_html  # ✅ nuevo

ResolverCaptcha = Callable[[bytes], str]

class RuntController:
    def __init__(self):
        pass

    def consultar_ciudadano(
        self,
        params: ConsultaRuntParams,
        resolver_captcha: Optional[ResolverCaptcha] = None,
        debug: bool = True,
    ) -> ResultadoRunt:
        """
        Orquesta la consulta: recibe params de la vista, llama al servicio,
        parsea resultados y devuelve un ResultadoRunt.
        """

        html = run_runt_flow(
            tipo=params.tipo_documento,
            numero=params.numero_documento,
            headless=False,
            slow_mo=300,
            resolver_captcha=resolver_captcha,
            debug=debug,
            hold_after=False,  # recomendado: no bloquear aquí; la GUI ya gestiona la UX
        )

        # ✅ Caso SIN REGISTRO
        if html is None:
            if debug:
                print("⚠ Resultado: documento sin registro o persona no activa en RUNT.")
            return ResultadoRunt(raw_html=None, sin_registro=True)

        # ✅ Parseo
        parsed = parse_runt_html(html)
        secciones = parsed.get("secciones", {}) or {}

        # ✅ Detección simple de multas (si existe sección y trae algo)
        # Nota: el título exacto puede variar; intentamos varias claves tolerantes
        posibles_multas_keys = [
            "MULTAS E INFRACCIONES",
            "MULTAS",
            "INFRACCIONES",
        ]
        multas_data = None
        for k in posibles_multas_keys:
            if k in secciones:
                multas_data = secciones.get(k)
                break

        tiene_multas = None
        if multas_data is None:
            tiene_multas = False
        else:
            # si es lista con al menos un item o dict con algún contenido, asumimos que sí hay info
            if isinstance(multas_data, list):
                tiene_multas = len(multas_data) > 0
            elif isinstance(multas_data, dict):
                tiene_multas = len(multas_data) > 0
            else:
                tiene_multas = bool(str(multas_data).strip())

        return ResultadoRunt(
            nombre=parsed.get("nombre_completo"),
            estado_licencia=parsed.get("estado_conductor"),
            tiene_multas=tiene_multas,
            secciones=secciones,
            raw_html=html,
            sin_registro=False,
        )