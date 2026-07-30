import threading
from typing import Callable, Optional

from config.settings import get_settings
from controllers.persistencia_post_consulta import intentar_persistir_resultado
from controllers.runt_controller import RuntController, ResolverCaptcha
from controllers.simit_controller import SimitController
from models.consulta_models import ConsultaParams, ResultadoConsulta
from models.runt_models import ConsultaRuntParams, ResultadoRunt
from models.simit_models import ConsultaSimitParams, ResultadoSimit
from utils.logging_setup import (
    ensure_correlation_id,
    get_logger,
    new_correlation_id,
    set_correlation_id,
)

logger = get_logger(__name__)

# Callback opcional: (fuente, estado) p. ej. ("RUNT", "en_curso") / ("SIMIT", "ok").
ProgresoCallback = Callable[[str, str], None]


class ConsultaController:
    def __init__(self) -> None:
        self._runt = RuntController()
        self._simit = SimitController()

    @staticmethod
    def _emitir_progreso(
        on_progreso: Optional[ProgresoCallback],
        fuente: str,
        estado: str,
    ) -> None:
        if on_progreso is None:
            return
        try:
            on_progreso(fuente, estado)
        except Exception:
            logger.debug("Callback de progreso falló", exc_info=True)

    @staticmethod
    def _aplicar_resultado_runt(
        destino: ResultadoConsulta,
        resultado: ResultadoRunt,
    ) -> None:
        destino.resultado_runt = resultado
        if resultado.error:
            destino.error_runt = resultado.error
            logger.error("Error RUNT en ResultadoConsulta: %s", resultado.error)

    @staticmethod
    def _aplicar_resultado_simit(
        destino: ResultadoConsulta,
        resultado: ResultadoSimit,
    ) -> None:
        destino.resultado_simit = resultado
        if resultado.error:
            destino.error_simit = resultado.error
            logger.error("Error SIMIT en ResultadoConsulta: %s", resultado.error)

    def consultar(
        self,
        params: ConsultaParams,
        resolver_captcha: Optional[ResolverCaptcha] = None,
        debug: Optional[bool] = None,
        on_progreso: Optional[ProgresoCallback] = None,
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
        resultado.marcar_inicio(
            correlation_id=cid,
            tipo_documento=params.tipo_documento,
        )

        if params.modo == "PLACA":
            self._emitir_progreso(on_progreso, "RUNT", "omitido")
            self._emitir_progreso(on_progreso, "SIMIT", "en_curso")
            simit = self._simit.consultar(
                ConsultaSimitParams(
                    identificador=params.identificador,
                    modo="PLACA",
                ),
                debug=debug,
            )
            self._aplicar_resultado_simit(resultado, simit)
            resultado.finalizar()
            self._emitir_progreso(
                on_progreso, "SIMIT", resultado.estado_fuente_simit()
            )
            intentar_persistir_resultado(resultado)
            logger.info(
                "Consulta PLACA finalizada cid=%s estado_simit=%s estado_global=%s "
                "persistido=%s",
                cid,
                resultado.estado_fuente_simit(),
                resultado.estado_global,
                resultado.persistido,
            )
            return resultado

        # Modo DOCUMENTO: SIMIT en hilo aparte; RUNT en el hilo actual
        # (necesario para que el diálogo de CAPTCHA funcione en Qt).
        # Reintento por fuente individual no se expone: CAPTCHA + este
        # paralelismo hacen inseguro mezclar resultados parciales en UI.
        runt_params = ConsultaRuntParams(
            tipo_documento=params.tipo_documento or "CC",
            numero_documento=params.identificador,
        )
        simit_params = ConsultaSimitParams(
            identificador=params.identificador,
            modo="DOCUMENTO",
        )

        simit_holder: dict = {"result": None}

        def _consultar_simit() -> None:
            set_correlation_id(cid)
            self._emitir_progreso(on_progreso, "SIMIT", "en_curso")
            # El controller no debe propagar; red de seguridad por si acaso.
            try:
                simit_holder["result"] = self._simit.consultar(
                    params=simit_params, debug=debug
                )
            except Exception as e:
                from models.exceptions import FUENTE_SIMIT, mensaje_accionable_fuente

                msg = mensaje_accionable_fuente(FUENTE_SIMIT, e)
                logger.error("Error inesperado hilo SIMIT: %s", msg, exc_info=True)
                simit_holder["result"] = ResultadoSimit(error=msg)

        self._emitir_progreso(on_progreso, "RUNT", "en_curso")
        simit_thread = threading.Thread(target=_consultar_simit, daemon=True)
        simit_thread.start()

        ensure_correlation_id()
        runt = self._runt.consultar_ciudadano(
            params=runt_params,
            resolver_captcha=resolver_captcha,
            debug=debug,
        )
        self._aplicar_resultado_runt(resultado, runt)
        self._emitir_progreso(on_progreso, "RUNT", resultado.estado_fuente_runt())

        simit_thread.join()
        if simit_holder["result"] is not None:
            self._aplicar_resultado_simit(resultado, simit_holder["result"])
        self._emitir_progreso(on_progreso, "SIMIT", resultado.estado_fuente_simit())

        resultado.finalizar()
        intentar_persistir_resultado(resultado)
        logger.info(
            "Consulta DOCUMENTO finalizada cid=%s estado_runt=%s estado_simit=%s "
            "estado_global=%s persistido=%s",
            cid,
            resultado.estado_fuente_runt(),
            resultado.estado_fuente_simit(),
            resultado.estado_global,
            resultado.persistido,
        )
        return resultado
