# views/console_view.py

import argparse
from pathlib import Path

from models.runt_models import ConsultaRuntParams
from controllers.runt_controller import RuntController

def resolver_captcha_consola(image_bytes: bytes) -> str:
    """
    Vista de consola para resolver el captcha:
    guarda la imagen en un archivo y pide texto por input().
    """
    tmp = Path("captcha.png").absolute()
    tmp.write_bytes(image_bytes)
    print(f"🖼 CAPTCHA guardado en: {tmp}")
    return input("👉 Texto del CAPTCHA: ").strip()

def main():
    parser = argparse.ArgumentParser(description="Automatiza la consulta en RUNT (captcha manual).")
    parser.add_argument("--tipo", required=True, help="Tipo de documento (CC, CE, NIT, etc.)")
    parser.add_argument("--numero", required=True, help="Número de documento")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Desactivar mensajes de depuración.")
    args = parser.parse_args()

    controller = RuntController()

    params = ConsultaRuntParams(
        tipo_documento=args.tipo,
        numero_documento=args.numero,
    )

    resultado = controller.consultar_ciudadano(
        params=params,
        resolver_captcha=resolver_captcha_consola,
        debug=args.debug,
    )

    print("✅ Consulta completada (resultado aún sin parsear):")
    print(resultado)
