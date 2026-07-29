from typing import Callable, Optional

from config.settings import get_settings
from models.exceptions import FUENTE_RUNT, mensaje_accionable_fuente
from models.runt_models import ConsultaRuntParams, ResultadoRunt
from services.runt_playwright import run_runt_flow
from services.runt_parser import parse_runt_html
from utils.logging_setup import ensure_correlation_id, get_logger

ResolverCaptcha = Callable[[bytes], str]

logger = get_logger(__name__)


class RuntController:
    def __init__(self) -> None:
        pass

    def consultar_ciudadano(
        self,
        params: ConsultaRuntParams,
        resolver_captcha: Optional[ResolverCaptcha] = None,
        debug: Optional[bool] = None,
    ) -> ResultadoRunt:
        """
        Orquesta la consulta RUNT.

        No propaga excepciones operativas: las representa en ``ResultadoRunt.error``
        para mantener el mismo contrato que SIMIT.
        """
        settings = get_settings()
        if debug is None:
            debug = settings.debug

        cid = ensure_correlation_id()
        logger.info(
            "Iniciando consulta RUNT tipo=%s documento=%s cid=%s",
            params.tipo_documento,
            params.numero_documento,
            cid,
        )

        try:
            html = run_runt_flow(
                tipo=params.tipo_documento,
                numero=params.numero_documento,
                headless=settings.browser_headless,
                slow_mo=settings.runt_slow_mo_ms,
                resolver_captcha=resolver_captcha,
                debug=debug,
                hold_after=False,
            )

            if html is None:
                logger.info(
                    "Resultado RUNT: documento sin registro o persona no activa."
                )
                return ResultadoRunt(raw_html=None, sin_registro=True)

            parsed = parse_runt_html(html)
            secciones = parsed.get("secciones", {}) or {}

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

            if multas_data is None:
                tiene_multas = False
            elif isinstance(multas_data, list):
                tiene_multas = len(multas_data) > 0
            elif isinstance(multas_data, dict):
                tiene_multas = len(multas_data) > 0
            else:
                tiene_multas = bool(str(multas_data).strip())

            logger.info(
                "Consulta RUNT OK nombre=%s secciones=%s",
                parsed.get("nombre_completo"),
                list(secciones.keys()),
            )
            return ResultadoRunt(
                nombre=parsed.get("nombre_completo"),
                estado_licencia=parsed.get("estado_conductor"),
                tiene_multas=tiene_multas,
                secciones=secciones,
                raw_html=html,
                sin_registro=False,
            )
        except Exception as e:
            msg = mensaje_accionable_fuente(FUENTE_RUNT, e)
            logger.error("Error consulta RUNT: %s", msg, exc_info=True)
            return ResultadoRunt(error=msg)
