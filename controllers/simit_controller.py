from models.simit_models import ConsultaSimitParams, ResultadoSimit
from services.simit_playwright import run_simit_flow
from services.simit_parser import parse_simit_html


class SimitController:
    def consultar(
        self,
        params: ConsultaSimitParams,
        debug: bool = True,
    ) -> ResultadoSimit:
        try:
            html = run_simit_flow(
                identificador=params.identificador,
                headless=False,
                slow_mo=200,
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
