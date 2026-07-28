import threading
from typing import Optional

from config.settings import get_settings
from controllers.runt_controller import RuntController, ResolverCaptcha
from controllers.simit_controller import SimitController
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.runt_models import ConsultaRuntParams
from models.simit_models import ConsultaSimitParams


class ConsultaController:
    def __init__(self):
        self._runt = RuntController()
        self._simit = SimitController()

    def consultar(
        self,
        params: ConsultaParams,
        resolver_captcha: Optional[ResolverCaptcha] = None,
        debug: Optional[bool] = None,
    ) -> ResultadoConsulta:
        if debug is None:
            debug = get_settings().debug

        resultado = ResultadoConsulta(
            modo=params.modo,
            identificador=params.identificador,
        )

        if params.modo == "PLACA":
            resultado.resultado_simit = self._simit.consultar(
                ConsultaSimitParams(
                    identificador=params.identificador,
                    modo="PLACA",
                ),
                debug=debug,
            )
            if resultado.resultado_simit.error:
                resultado.error_simit = resultado.resultado_simit.error
            return resultado

        # Modo DOCUMENTO: SIMIT en hilo aparte; RUNT en el hilo actual
        # (necesario para que el diálogo de CAPTCHA funcione en Qt).
        runt_params = ConsultaRuntParams(
            tipo_documento=params.tipo_documento or "CC",
            numero_documento=params.identificador,
        )
        simit_params = ConsultaSimitParams(
            identificador=params.identificador,
            modo="DOCUMENTO",
        )

        simit_holder: dict = {"result": None, "error": None}

        def _consultar_simit():
            try:
                simit_holder["result"] = self._simit.consultar(
                    params=simit_params, debug=debug
                )
            except Exception as e:
                simit_holder["error"] = str(e)

        simit_thread = threading.Thread(target=_consultar_simit, daemon=True)
        simit_thread.start()

        try:
            resultado.resultado_runt = self._runt.consultar_ciudadano(
                params=runt_params,
                resolver_captcha=resolver_captcha,
                debug=debug,
            )
        except Exception as e:
            resultado.error_runt = str(e)

        simit_thread.join()

        if simit_holder["error"]:
            resultado.error_simit = simit_holder["error"]
        elif simit_holder["result"] is not None:
            resultado.resultado_simit = simit_holder["result"]
            if simit_holder["result"].error:
                resultado.error_simit = simit_holder["result"].error

        return resultado
