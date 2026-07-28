# views/console_view.py

import argparse
import sys
from pathlib import Path

from config.settings import get_settings
from models.runt_models import ConsultaRuntParams
from controllers.runt_controller import RuntController
from utils.documento_validator import TIPOS_SOPORTADOS, validar_documento
from utils.logging_setup import (
    get_correlation_id,
    get_logger,
    new_correlation_id,
    set_correlation_id,
    setup_logging,
)

logger = get_logger(__name__)


def resolver_captcha_consola(image_bytes: bytes) -> str:
    """
    Vista de consola para resolver el captcha:
    guarda la imagen en un archivo y pide texto por input().
    """
    tmp = Path("captcha.png").absolute()
    tmp.write_bytes(image_bytes)
    # Interacción operador: se mantiene en stdout (no es diagnóstico de servicio).
    print(f"🖼 CAPTCHA guardado en: {tmp}")
    return input("👉 Texto del CAPTCHA: ").strip()


def main() -> None:
    setup_logging()
    settings = get_settings()
    tipos = ", ".join(sorted(TIPOS_SOPORTADOS))
    parser = argparse.ArgumentParser(
        description="Automatiza la consulta en RUNT (captcha manual).",
    )
    parser.add_argument(
        "--tipo",
        required=True,
        help=f"Tipo de documento ({tipos})",
    )
    parser.add_argument("--numero", required=True, help="Número de documento")
    parser.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        default=settings.debug,
        help="Desactivar mensajes de depuración.",
    )
    args = parser.parse_args()

    ok, tipo_norm, numero_norm, msg = validar_documento(args.tipo, args.numero)
    if not ok:
        print(f"Error de validación:\n{msg}", file=sys.stderr)
        raise SystemExit(2)

    set_correlation_id(new_correlation_id())
    logger.info(
        "CLI RUNT tipo=%s numero=%s cid=%s",
        tipo_norm,
        numero_norm,
        get_correlation_id(),
    )

    controller = RuntController()

    params = ConsultaRuntParams(
        tipo_documento=tipo_norm,
        numero_documento=numero_norm,
    )

    resultado = controller.consultar_ciudadano(
        params=params,
        resolver_captcha=resolver_captcha_consola,
        debug=args.debug,
    )

    # Salida orientada al operador (stdout).
    print("✅ Consulta completada:")
    print(f"Sin registro: {resultado.sin_registro}")
    print(f"Nombre: {resultado.nombre}")
    print(f"Estado conductor: {resultado.estado_licencia}")
    print(f"Tiene multas: {resultado.tiene_multas}")
    print("Secciones:", list((resultado.secciones or {}).keys()))
