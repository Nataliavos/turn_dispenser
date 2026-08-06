"""
Mappers de normalización v2: ResultadoConsulta → maestros + hechos tipados.

Solo hechos observados. Sin lógica de elegibilidad / apto / puede_tramitar.
Normalización de claves según docs/DB_DESIGN_V2.md §6.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from models.consulta_models import ResultadoConsulta
from models.runt_models import ResultadoRunt
from models.simit_models import AcuerdoPago, ComparendoMulta, ResultadoSimit
from utils.documento_validator import (
    normalizar_numero_documento,
    normalizar_tipo_documento,
)
from utils.placa_validator import normalizar_placa

_CLAVES_LICENCIAS: Tuple[str, ...] = ("LICENCIAS",)
_CLAVES_MULTAS_INFRACCIONES: Tuple[str, ...] = (
    "MULTAS E INFRACCIONES",
    "MULTAS",
    "INFRACCIONES",
)


@dataclass(frozen=True)
class FilaPersona:
    tipo_documento: str
    numero_documento: str
    nombre_completo: Optional[str] = None
    estado_persona: Optional[str] = None
    numero_inscripcion_runt: Optional[str] = None
    fecha_inscripcion_runt: Optional[str] = None
    atributos: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FilaVehiculo:
    placa: str
    atributos: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FilaVinculo:
    tipo_documento: str
    numero_documento: str
    placa: str
    fuente: str  # RUNT | SIMIT | SISTEMA


@dataclass(frozen=True)
class FilaLicencia:
    numero_licencia: Optional[str]
    categoria: Optional[str] = None
    estado: Optional[str] = None
    fecha_expedicion: Optional[str] = None
    fecha_vencimiento: Optional[str] = None
    atributos: Dict[str, Any] = field(default_factory=dict)
    fuente: str = "RUNT"


@dataclass(frozen=True)
class FilaInfraccionRunt:
    fingerprint: str
    placa: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[str] = None
    fecha: Optional[str] = None
    valor: Optional[Decimal] = None
    atributos: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FilaObligacionSimit:
    numero: Optional[str]
    fingerprint: Optional[str]
    tipo: Optional[str] = None
    placa: Optional[str] = None
    fecha_imposicion: Optional[str] = None
    notificacion: Optional[str] = None
    secretaria: Optional[str] = None
    infraccion: Optional[str] = None
    infraccion_descripcion: Optional[str] = None
    estado: Optional[str] = None
    valor: Optional[Decimal] = None
    valor_a_pagar: Optional[Decimal] = None
    atributos: Dict[str, Any] = field(default_factory=dict)
    fuente: str = "SIMIT"


@dataclass(frozen=True)
class FilaAcuerdoPagoSimit:
    numero_acuerdo: Optional[str]
    fingerprint: Optional[str]
    estado: Optional[str] = None
    valor: Optional[Decimal] = None
    atributos: Dict[str, Any] = field(default_factory=dict)
    fuente: str = "SIMIT"


@dataclass
class PlanNormalizacion:
    """Filas listas para upsert best-effort (capa B/C)."""

    persona: Optional[FilaPersona] = None
    vehiculos: List[FilaVehiculo] = field(default_factory=list)
    vinculos: List[FilaVinculo] = field(default_factory=list)
    licencias: List[FilaLicencia] = field(default_factory=list)
    infracciones_runt: List[FilaInfraccionRunt] = field(default_factory=list)
    obligaciones_simit: List[FilaObligacionSimit] = field(default_factory=list)
    acuerdos_pago_simit: List[FilaAcuerdoPagoSimit] = field(default_factory=list)


def fingerprint(*partes: Any) -> str:
    """Huella estable SHA-256 de campos clave (mayúsculas, trim)."""
    payload = "|".join(
        "" if p is None else str(p).strip().upper() for p in partes
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_monto_numeric(texto: Optional[str]) -> Optional[Decimal]:
    """
    Intenta parsear montos COL (puntos miles, coma decimal).

    Si no es parseable, retorna None (el texto puede ir a ``atributos``).
    """
    if texto is None:
        return None
    raw = str(texto).strip()
    if not raw:
        return None
    limpio = re.sub(r"[^\d,.\-]", "", raw)
    if not limpio or limpio in {".", ",", "-", "-.", "-,"}:
        return None
    # Formato COL típico: 1.234.567,89
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")
    elif "." in limpio:
        partes = limpio.split(".")
        # Si el último grupo tiene 3 dígitos → puntos de miles (604.100).
        # Si tiene 1–2 → decimal anglosajón (10.50).
        if len(partes[-1]) == 3:
            limpio = limpio.replace(".", "")
        elif limpio.count(".") > 1:
            limpio = limpio.replace(".", "")
    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def _strip_accents(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _as_opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    texto = str(value).strip()
    return texto or None


def dict_get_campo(fila: Mapping[str, Any], *candidatos: str) -> Optional[str]:
    """Busca clave exacta, casefold o sin tildes entre candidatos."""
    if not fila:
        return None
    keys_norm: Dict[str, Any] = {}
    for k, v in fila.items():
        keys_norm[_strip_accents(str(k)).casefold()] = v
    for cand in candidatos:
        if cand in fila:
            return _as_opt_str(fila[cand])
        v = keys_norm.get(_strip_accents(cand).casefold())
        if v is not None:
            return _as_opt_str(v)
    return None


def _filas_seccion(
    secciones: Mapping[str, Any], claves: Sequence[str]
) -> List[Dict[str, Any]]:
    for clave in claves:
        data = secciones.get(clave)
        if data is None:
            continue
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            # Un solo objeto label/valor: no es fila de licencia tipada.
            return []
    return []


def _placa_valida_o_none(texto: Optional[str]) -> Optional[str]:
    if not texto:
        return None
    placa = normalizar_placa(texto)
    return placa or None


def _persona_desde_documento(
    resultado: ResultadoConsulta,
) -> Optional[FilaPersona]:
    runt = resultado.resultado_runt
    tipo = normalizar_tipo_documento(
        (runt.tipo_documento if runt else None) or resultado.tipo_documento or ""
    )
    numero_raw = (
        (runt.numero_documento if runt else None)
        or (
            resultado.identificador
            if resultado.modo == "DOCUMENTO"
            else None
        )
    )
    if not tipo or not numero_raw:
        return None
    numero = normalizar_numero_documento(numero_raw)
    if not numero:
        return None
    atributos: Dict[str, Any] = {}
    if runt and runt.estado_licencia:
        atributos["estado_conductor_runt"] = runt.estado_licencia
    return FilaPersona(
        tipo_documento=tipo,
        numero_documento=numero,
        nombre_completo=_as_opt_str(runt.nombre if runt else None),
        estado_persona=_as_opt_str(runt.estado_persona if runt else None),
        numero_inscripcion_runt=_as_opt_str(
            runt.numero_inscripcion if runt else None
        ),
        fecha_inscripcion_runt=_as_opt_str(
            runt.fecha_inscripcion if runt else None
        ),
        atributos=atributos,
    )


def _persona_desde_cedula_simit(
    resultado: ResultadoConsulta,
) -> Optional[FilaPersona]:
    """PLACA + cédula en resumen SIMIT: maestro persona (tipo CC por etiqueta)."""
    simit = resultado.resultado_simit
    if simit is None or simit.resumen is None:
        return None
    cedula = _as_opt_str(simit.resumen.cedula)
    if not cedula:
        return None
    numero = normalizar_numero_documento(cedula)
    if not numero:
        return None
    return FilaPersona(
        tipo_documento="CC",
        numero_documento=numero,
        atributos={"tipo_documento_origen": "simit_cedula"},
    )


def _map_licencia(fila: Mapping[str, Any]) -> Optional[FilaLicencia]:
    numero = dict_get_campo(fila, "NÚMERO", "NUMERO", "NUMERO LICENCIA", "NÚMERO LICENCIA")
    categoria = dict_get_campo(fila, "CATEGORÍA", "CATEGORIA")
    estado = dict_get_campo(fila, "ESTADO")
    fecha_exp = dict_get_campo(
        fila, "FECHA EXPEDICIÓN", "FECHA EXPEDICION", "EXPEDICIÓN", "EXPEDICION"
    )
    fecha_ven = dict_get_campo(
        fila, "FECHA VENCIMIENTO", "VENCIMIENTO", "FECHA DE VENCIMIENTO"
    )
    tipados = {
        "NÚMERO",
        "NUMERO",
        "CATEGORÍA",
        "CATEGORIA",
        "ESTADO",
        "FECHA EXPEDICIÓN",
        "FECHA EXPEDICION",
        "FECHA VENCIMIENTO",
        "VENCIMIENTO",
    }
    atributos = {
        str(k): v
        for k, v in fila.items()
        if _strip_accents(str(k)).casefold()
        not in {_strip_accents(t).casefold() for t in tipados}
    }
    if not any([numero, categoria, estado, fecha_exp, fecha_ven, atributos]):
        return None
    if numero is None and not atributos:
        # UK parcial por md5(atributos): asegurar payload no vacío.
        atributos = {"fila_cruda": dict(fila)}
    return FilaLicencia(
        numero_licencia=numero,
        categoria=categoria,
        estado=estado,
        fecha_expedicion=fecha_exp,
        fecha_vencimiento=fecha_ven,
        atributos=atributos or ({"fila_cruda": dict(fila)} if numero is None else {}),
    )


def _map_infraccion_runt(fila: Mapping[str, Any]) -> Optional[FilaInfraccionRunt]:
    numero = dict_get_campo(fila, "NÚMERO", "NUMERO")
    descripcion = dict_get_campo(fila, "DESCRIPCIÓN", "DESCRIPCION")
    estado = dict_get_campo(fila, "ESTADO")
    fecha = dict_get_campo(fila, "FECHA")
    placa_raw = dict_get_campo(fila, "PLACA")
    placa = _placa_valida_o_none(placa_raw)
    valor_txt = dict_get_campo(fila, "VALOR", "VALOR A PAGAR")
    valor = parse_monto_numeric(valor_txt)
    atributos = {str(k): v for k, v in fila.items()}
    fp = fingerprint("INFRACCION_RUNT", numero, descripcion, estado, fecha, placa)
    if not any([numero, descripcion, estado, fecha, placa, valor_txt]):
        return None
    return FilaInfraccionRunt(
        fingerprint=fp,
        placa=placa,
        descripcion=descripcion,
        estado=estado,
        fecha=fecha,
        valor=valor,
        atributos=atributos,
    )


def _map_obligacion(
    item: ComparendoMulta,
) -> Optional[FilaObligacionSimit]:
    numero = _as_opt_str(item.numero)
    placa = _placa_valida_o_none(item.placa)
    valor = parse_monto_numeric(item.valor)
    valor_pagar = parse_monto_numeric(item.valor_a_pagar)
    atributos: Dict[str, Any] = {}
    if item.valor is not None and valor is None:
        atributos["valor_texto"] = item.valor
    if item.valor_a_pagar is not None and valor_pagar is None:
        atributos["valor_a_pagar_texto"] = item.valor_a_pagar
    fp: Optional[str] = None
    if not numero:
        fp = fingerprint(
            "OBLIGACION_SIMIT",
            item.tipo,
            item.fecha_imposicion,
            placa,
            item.infraccion,
            item.estado,
            item.valor,
            item.valor_a_pagar,
        )
    if not numero and not fp:
        return None
    if not any(
        [
            numero,
            item.tipo,
            item.fecha_imposicion,
            placa,
            item.infraccion,
            item.estado,
            item.valor,
        ]
    ):
        return None
    return FilaObligacionSimit(
        numero=numero,
        fingerprint=fp,
        tipo=_as_opt_str(item.tipo),
        placa=placa,
        fecha_imposicion=_as_opt_str(item.fecha_imposicion),
        notificacion=_as_opt_str(item.notificacion),
        secretaria=_as_opt_str(item.secretaria),
        infraccion=_as_opt_str(item.infraccion),
        infraccion_descripcion=_as_opt_str(item.infraccion_descripcion),
        estado=_as_opt_str(item.estado),
        valor=valor,
        valor_a_pagar=valor_pagar,
        atributos=atributos,
    )


def _map_acuerdo(item: AcuerdoPago) -> Optional[FilaAcuerdoPagoSimit]:
    numero = _as_opt_str(item.numero_acuerdo)
    valor = parse_monto_numeric(item.valor_acuerdo) or parse_monto_numeric(
        item.valor_a_pagar
    )
    atributos: Dict[str, Any] = {}
    for key, val in (
        ("fecha", item.fecha),
        ("secretaria", item.secretaria),
        ("valor_acuerdo", item.valor_acuerdo),
        ("pendiente", item.pendiente),
        ("cuota", item.cuota),
        ("valor_a_pagar", item.valor_a_pagar),
        ("descuento", item.descuento),
    ):
        if val is not None:
            atributos[key] = val
    fp: Optional[str] = None
    if not numero:
        fp = fingerprint(
            "ACUERDO_SIMIT",
            item.fecha,
            item.secretaria,
            item.valor_acuerdo,
            item.pendiente,
            item.cuota,
        )
    if not numero and not fp:
        return None
    if not numero and not atributos:
        return None
    return FilaAcuerdoPagoSimit(
        numero_acuerdo=numero,
        fingerprint=fp,
        estado=None,
        valor=valor,
        atributos=atributos,
    )


def plan_normalizacion_desde_resultado(
    resultado: ResultadoConsulta,
) -> PlanNormalizacion:
    """
    Construye el plan de upsert maestros/hechos a partir del resultado en memoria.

    No escribe BD. Degradación defensiva: omitir filas no usables.
    """
    plan = PlanNormalizacion()
    placas: Dict[str, FilaVehiculo] = {}
    vinculos_keys: set[Tuple[str, str, str]] = set()

    def _add_placa(placa: Optional[str], **attrs: Any) -> None:
        if not placa:
            return
        existentes = placas.get(placa)
        if existentes is None:
            placas[placa] = FilaVehiculo(placa=placa, atributos=dict(attrs))
        elif attrs:
            merged = dict(existentes.atributos)
            merged.update({k: v for k, v in attrs.items() if v is not None})
            placas[placa] = FilaVehiculo(placa=placa, atributos=merged)

    def _add_vinculo(
        tipo: str, numero: str, placa: str, fuente: str
    ) -> None:
        key = (tipo, numero, placa)
        if key in vinculos_keys:
            return
        vinculos_keys.add(key)
        plan.vinculos.append(
            FilaVinculo(
                tipo_documento=tipo,
                numero_documento=numero,
                placa=placa,
                fuente=fuente,
            )
        )

    # --- Persona ---
    if resultado.modo == "DOCUMENTO":
        plan.persona = _persona_desde_documento(resultado)
    else:
        plan.persona = _persona_desde_cedula_simit(resultado)
        # Si no hay cédula SIMIT, no forzar persona en modo PLACA.

    # --- Vehículo modo PLACA ---
    if resultado.modo == "PLACA":
        _add_placa(_placa_valida_o_none(resultado.identificador))

    # --- Hechos RUNT ---
    runt: Optional[ResultadoRunt] = resultado.resultado_runt
    if runt and not runt.sin_registro:
        for fila in _filas_seccion(runt.secciones, _CLAVES_LICENCIAS):
            lic = _map_licencia(fila)
            if lic is not None:
                plan.licencias.append(lic)
        for fila in _filas_seccion(runt.secciones, _CLAVES_MULTAS_INFRACCIONES):
            infr = _map_infraccion_runt(fila)
            if infr is None:
                continue
            plan.infracciones_runt.append(infr)
            if infr.placa and plan.persona is not None:
                _add_placa(infr.placa)
                _add_vinculo(
                    plan.persona.tipo_documento,
                    plan.persona.numero_documento,
                    infr.placa,
                    "RUNT",
                )

    # --- Hechos SIMIT ---
    simit: Optional[ResultadoSimit] = resultado.resultado_simit
    if simit is not None and not simit.sin_registro:
        sin_pendientes = bool(
            simit.resumen and simit.resumen.sin_pendientes
        )
        if not sin_pendientes:
            for item in simit.comparendos_multas:
                obl = _map_obligacion(item)
                if obl is None:
                    continue
                plan.obligaciones_simit.append(obl)
                if obl.placa:
                    _add_placa(obl.placa)
                    if plan.persona is not None:
                        _add_vinculo(
                            plan.persona.tipo_documento,
                            plan.persona.numero_documento,
                            obl.placa,
                            "SIMIT",
                        )
        # Acuerdos: tipados aunque sin_pendientes (lista vacía = cero filas).
        if not sin_pendientes or simit.acuerdos_pago:
            for item in simit.acuerdos_pago:
                acu = _map_acuerdo(item)
                if acu is not None:
                    plan.acuerdos_pago_simit.append(acu)

        # PLACA + cédula → vínculo con placa de consulta
        if (
            resultado.modo == "PLACA"
            and plan.persona is not None
            and resultado.identificador
        ):
            placa_consulta = _placa_valida_o_none(resultado.identificador)
            if placa_consulta:
                _add_placa(placa_consulta)
                _add_vinculo(
                    plan.persona.tipo_documento,
                    plan.persona.numero_documento,
                    placa_consulta,
                    "SIMIT",
                )

    plan.vehiculos = list(placas.values())

    # Licencias / infracciones RUNT requieren persona; si no hay, se omiten.
    if plan.persona is None:
        plan.licencias = []
        plan.infracciones_runt = []
        plan.vinculos = []

    return plan
