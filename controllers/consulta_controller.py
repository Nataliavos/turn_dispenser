import threading
from typing import Optional

from config.settings import get_settings
from controllers.runt_controller import RuntController, ResolverCaptcha
from controllers.simit_controller import SimitController
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.runt_models import ConsultaRuntParams
from models.simit_models import ConsultaSimitParams
from utils.logging_setup import (
    ensure_correlation_id,
    get_logger,
    new_correlation_id,
    set_correlation_id,
)

logger = get_logger(__name__)


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

        cid = new_correlation_id()
        set_correlation_id(cid)
        logger.info(
            "Consulta iniciada modo=%s identificador=%s cid=%s",
            params.modo,
            params.identificador,
            cid,
        )

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
                logger.error("Error SIMIT (PLACA): %s", resultado.error_simit)
            logger.info("Consulta PLACA finalizada cid=%s", cid)
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

        def _consultar_simit() -> None:
            set_correlation_id(cid)
            try:
                simit_holder["result"] = self._simit.consultar(
                    params=simit_params, debug=debug
                )
            except Exception as e:
                logger.error("Error hilo SIMIT: %s", e, exc_info=True)
                simit_holder["error"] = str(e)

        simit_thread = threading.Thread(target=_consultar_simit, daemon=True)
        simit_thread.start()

        try:
            ensure_correlation_id()
            resultado.resultado_runt = self._runt.consultar_ciudadano(
                params=runt_params,
                resolver_captcha=resolver_captcha,
                debug=debug,
            )
        except Exception as e:
            logger.error("Error consulta RUNT: %s", e, exc_info=True)
            resultado.error_runt = str(e)

        simit_thread.join()

        if simit_holder["error"]:
            resultado.error_simit = simit_holder["error"]
            logger.error("Error SIMIT (DOCUMENTO): %s", resultado.error_simit)
        elif simit_holder["result"] is not None:
            resultado.resultado_simit = simit_holder["result"]
            if simit_holder["result"].error:
                resultado.error_simit = simit_holder["result"].error
                logger.error("Error SIMIT (DOCUMENTO): %s", resultado.error_simit)

        logger.info(
            "Consulta DOCUMENTO finalizada cid=%s error_runt=%s error_simit=%s",
            cid,
            bool(resultado.error_runt),
            bool(resultado.error_simit),
        )
        return resultado
