from typing import Optional

from config.settings import get_settings
from models.simit_models import ConsultaSimitParams, ResultadoSimit
from services.simit_playwright import run_simit_flow
from services.simit_parser import parse_simit_html


class SimitController:
    def consultar(
        self,
        params: ConsultaSimitParams,
        debug: Optional[bool] = None,
    ) -> ResultadoSimit:
        settings = get_settings()
        if debug is None:
            debug = settings.debug

        try:
            html = run_simit_flow(
                identificador=params.identificador,
                headless=settings.browser_headless,
                slow_mo=settings.simit_slow_mo_ms,
                debug=debug,
            )

            resultado = parse_simit_html(
                html,
                identificador=params.identificador,
                modo=params.modo,
            )
            return resultado

        except Exception as e:
            return ResultadoSimit(error=str(e))
