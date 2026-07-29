from typing import Callable

from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import ResultadoSimit

EmitFn = Callable[[str], None]

_ETIQUETAS_ESTADO = {
    "ok": "OK",
    "error": "error",
    "sin_registro": "sin registro",
    "sin_pendientes": "sin pendientes",
    "omitido": "—",
}


def etiqueta_estado(codigo: str) -> str:
    return _ETIQUETAS_ESTADO.get(codigo, codigo)


def resumen_estados_consulta(resultado: ResultadoConsulta) -> str:
    """Texto corto para label de estado en GUI (simétrico por fuente)."""
    if resultado.modo == "PLACA":
        return f"SIMIT: {etiqueta_estado(resultado.estado_fuente_simit())}"
    return (
        f"RUNT: {etiqueta_estado(resultado.estado_fuente_runt())} | "
        f"SIMIT: {etiqueta_estado(resultado.estado_fuente_simit())}"
    )


def formatear_resultado_consulta(resultado: ResultadoConsulta, emit: EmitFn) -> None:
    """Presenta errores y datos por fuente con la misma semántica."""
    if resultado.error_runt:
        emit(f"❌ Error RUNT: {resultado.error_runt}")
    elif resultado.resultado_runt is not None:
        formatear_resultado_runt(resultado.resultado_runt, emit)

    if resultado.error_simit:
        emit(f"❌ Error SIMIT: {resultado.error_simit}")
    elif resultado.resultado_simit is not None:
        formatear_resultado_simit(resultado.resultado_simit, emit)


def formatear_resultado_runt(resultado: ResultadoRunt, emit: EmitFn) -> None:
    emit("\n══════════ RUNT ══════════")

    if resultado.error:
        emit(f"❌ Error RUNT: {resultado.error}")
        return

    if resultado.sin_registro:
        emit("Sin registro ACTIVO en RUNT.")
        return

    emit(f"Nombre: {resultado.nombre}")
    emit(f"Estado conductor: {resultado.estado_licencia}")
    emit(f"Tiene multas (RUNT): {resultado.tiene_multas}")

    secciones = resultado.secciones or {}
    for titulo, contenido in secciones.items():
        emit(f"\n--- {titulo} ---")
        _formatear_contenido(contenido, emit)


def formatear_resultado_simit(resultado: ResultadoSimit, emit: EmitFn) -> None:
    emit("\n══════════ SIMIT ══════════")

    if resultado.error:
        emit(f"❌ Error SIMIT: {resultado.error}")
        return

    if resultado.sin_registro:
        emit("No se detectaron resultados en SIMIT.")
        return

    resumen = resultado.resumen
    if resumen and resumen.sin_pendientes and not resultado.comparendos_multas:
        emit("Sin comparendos, multas ni acuerdos pendientes en SIMIT.")
        if resumen.mensaje_estado:
            emit(f"Mensaje portal: {resumen.mensaje_estado}")

    if resumen:
        emit(f"Identificador: {resumen.identificador}")
        if resumen.cedula:
            emit(f"Cédula: {resumen.cedula}")
        emit(f"Comparendos: {resumen.comparendos}")
        emit(f"Multas: {resumen.multas}")
        emit(f"Acuerdos de pago: {resumen.acuerdos_pago}")
        emit(f"Total: {resumen.total}")

    if resultado.comparendos_multas:
        emit(f"\n--- Comparendos y Multas ({len(resultado.comparendos_multas)}) ---")
        for i, item in enumerate(resultado.comparendos_multas, start=1):
            emit(f"  Registro #{i}")
            emit(f"    Número: {item.numero}")
            emit(f"    Tipo: {item.tipo}")
            emit(f"    Fecha imposición: {item.fecha_imposicion}")
            emit(f"    Placa: {item.placa}")
            emit(f"    Secretaría: {item.secretaria}")
            emit(f"    Infracción: {item.infraccion}")
            if item.infraccion_descripcion:
                emit(f"    Descripción: {item.infraccion_descripcion}")
            emit(f"    Estado: {item.estado}")
            emit(f"    Valor: {item.valor}")
            emit(f"    Valor a pagar: {item.valor_a_pagar}")

        if resultado.total_comparendos_multas:
            t = resultado.total_comparendos_multas
            emit(f"  Total ({t.cantidad}): {t.valor or ''}")

    hay_acuerdos = (
        resultado.acuerdos_pago
        or resultado.total_acuerdos_pago
        or (resumen and resumen.acuerdos_pago > 0)
    )
    if hay_acuerdos:
        cantidad = len(resultado.acuerdos_pago) or (
            resultado.total_acuerdos_pago.cantidad
            if resultado.total_acuerdos_pago
            else (resumen.acuerdos_pago if resumen else 0)
        )
        emit(f"\n--- Acuerdos de pago ({cantidad}) ---")
        for i, item in enumerate(resultado.acuerdos_pago, start=1):
            emit(f"  Acuerdo #{i}")
            emit(f"    Número: {item.numero_acuerdo}")
            emit(f"    Fecha: {item.fecha}")
            emit(f"    Secretaría: {item.secretaria}")
            emit(f"    Valor acuerdo: {item.valor_acuerdo}")
            emit(f"    Pendiente: {item.pendiente}")
            emit(f"    Cuota: {item.cuota}")
            emit(f"    Valor a pagar: {item.valor_a_pagar}")

        if resultado.total_acuerdos_pago:
            t = resultado.total_acuerdos_pago
            emit(f"  Total acuerdos ({t.cantidad}): {t.valor or ''}")


def _formatear_contenido(contenido, emit: EmitFn) -> None:
    if contenido is None:
        emit("Sin información.")
    elif isinstance(contenido, list):
        for i, item in enumerate(contenido, start=1):
            emit(f"  Registro #{i}")
            if isinstance(item, dict):
                for k, v in item.items():
                    emit(f"    {k}: {v}")
            else:
                emit(f"    {item}")
    elif isinstance(contenido, dict):
        for k, v in contenido.items():
            emit(f"  {k}: {v}")
    else:
        emit(f"  {contenido}")
