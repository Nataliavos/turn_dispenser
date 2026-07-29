from typing import Optional

from config.settings import get_settings
from models.exceptions import FUENTE_SIMIT, mensaje_accionable_fuente
from models.simit_models import ConsultaSimitParams, ResultadoSimit
from services.simit_playwright import run_simit_flow
from services.simit_parser import parse_simit_html
from utils.logging_setup import ensure_correlation_id, get_logger

logger = get_logger(__name__)


class SimitController:
    def consultar(
        self,
        params: ConsultaSimitParams,
        debug: Optional[bool] = None,
    ) -> ResultadoSimit:
        """
        Orquesta la consulta SIMIT.

        No propaga excepciones operativas: las representa en ``ResultadoSimit.error``.
        """
        settings = get_settings()
        if debug is None:
            debug = settings.debug

        cid = ensure_correlation_id()
        logger.info(
            "Iniciando consulta SIMIT modo=%s identificador=%s cid=%s",
            params.modo,
            params.identificador,
            cid,
        )

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

            # Vacío / sin pendientes no es error operativo.
            if resultado.error:
                logger.error("Resultado SIMIT con error: %s", resultado.error)
            elif resultado.sin_registro:
                logger.info("Consulta SIMIT sin resultados detectados.")
            elif resultado.resumen and resultado.resumen.sin_pendientes:
                logger.info("Consulta SIMIT OK (sin pendientes).")
            else:
                logger.info("Consulta SIMIT OK.")
            return resultado

        except Exception as e:
            msg = mensaje_accionable_fuente(FUENTE_SIMIT, e)
            logger.error("Error en consulta SIMIT: %s", msg, exc_info=True)
            return ResultadoSimit(error=msg)
