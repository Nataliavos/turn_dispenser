# services/simit_parser.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from models.simit_models import (
    AcuerdoPago,
    ComparendoMulta,
    ResumenSimit,
    ResultadoSimit,
    TotalSeccion,
)

_MENSAJES_IGNORAR = re.compile(
    r"ingresa el correo|correo electr[oó]nico|enviar el estado de cuenta",
    re.I,
)


def _clean_text(s: str) -> str:
    return " ".join((s or "").split()).strip()


def _parse_int(value: Optional[str]) -> int:
    if not value:
        return 0
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def _extract_currency(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"\$\s*[\d.,]+", text)
    return match.group(0) if match else _clean_text(text)


def _cell_visible_text(td: Optional[Tag]) -> Optional[str]:
    """Extrae texto visible de una celda, omitiendo popovers ocultos y enlaces auxiliares."""
    if td is None:
        return None

    clone = BeautifulSoup(str(td), "html.parser").find("td")
    if clone is None:
        return None

    for tag in clone.find_all(style=re.compile(r"display\s*:\s*none", re.I)):
        tag.decompose()
    for tag in clone.find_all(id=re.compile(r"popover", re.I)):
        if "none" in (tag.get("style") or "").lower():
            tag.decompose()
    for tag in clone.find_all("p"):
        tag.decompose()

    text = _clean_text(clone.get_text(" ", strip=True))
    return text if text else None


def _extract_label_strong_pairs(container) -> Dict[str, Optional[str]]:
    data: Dict[str, Optional[str]] = {}
    if container is None:
        return data

    for lab in container.find_all("label"):
        key = _clean_text(lab.get_text(" ", strip=True)).replace(":", "").upper()
        if not key:
            continue

        value = None
        parent = lab.parent
        if parent:
            strong = parent.find("strong")
            if strong:
                value = _clean_text(strong.get_text(" ", strip=True))
            else:
                sib = parent.find_next_sibling()
                if sib:
                    strong = sib.find("strong")
                    value = _clean_text((strong or sib).get_text(" ", strip=True))

        if not value:
            nxt = lab.find_next("strong")
            if nxt:
                value = _clean_text(nxt.get_text(" ", strip=True))

        data[key] = value if value else None

    return data


def _parse_resumen(soup: BeautifulSoup, identificador: str, modo: str) -> ResumenSimit:
    resumen_div = soup.find(id="resumenEstadoCuenta")
    pairs = _extract_label_strong_pairs(resumen_div) if resumen_div else {}

    comparendos = _parse_int(pairs.get("COMPARENDOS"))
    multas = _parse_int(pairs.get("MULTAS"))
    acuerdos = _parse_int(pairs.get("ACUERDOS DE PAGO"))
    cedula = pairs.get("CÉDULA") or pairs.get("CEDULA")
    total = pairs.get("TOTAL")

    mensaje = None
    for text_node in soup.find_all(string=re.compile(
        r"No tienes comparendos|no posee a la fecha pendientes",
        re.I,
    )):
        candidato = _clean_text(str(text_node))
        if len(candidato) > 20 and not _MENSAJES_IGNORAR.search(candidato):
            mensaje = candidato
            break

    sin_pendientes = (
        comparendos == 0 and multas == 0 and acuerdos == 0
    ) or bool(mensaje)

    return ResumenSimit(
        identificador=identificador,
        modo=modo,
        comparendos=comparendos,
        multas=multas,
        acuerdos_pago=acuerdos,
        cedula=cedula or (identificador if modo == "DOCUMENTO" else None),
        total=total,
        mensaje_estado=mensaje,
        sin_pendientes=sin_pendientes,
    )


def _cell_by_label(row, label: str) -> Optional[str]:
    td = row.find("td", attrs={"data-label": label})
    return _cell_visible_text(td)


def _parse_infraccion(tr) -> tuple[Optional[str], Optional[str]]:
    inf_td = tr.find("td", attrs={"data-label": "Infracción"})
    if not inf_td:
        return None, None

    codigo = None
    descripcion = None
    popover = inf_td.find(attrs={"data-content": True})
    if popover:
        descripcion = popover.get("data-content", "").strip().strip('"')
        label = popover.find("label")
        if label:
            codigo = _clean_text(label.get_text())
        if not codigo:
            span = popover.find("span")
            if span:
                codigo = _clean_text(span.get_text())

    if not codigo:
        codigo = _cell_visible_text(inf_td)

    return codigo, descripcion


def _parse_estado(tr) -> Optional[str]:
    td = tr.find("td", attrs={"data-label": "Estado"})
    if not td:
        return None
    for p in td.find_all("p"):
        p.decompose()
    return _clean_text(td.get_text(" ", strip=True)) or None


def _parse_comparendos_multas(soup: BeautifulSoup) -> List[ComparendoMulta]:
    table = soup.find(id="multaTable")
    if not table:
        return []

    rows = table.find("tbody")
    if not rows:
        return []

    result: List[ComparendoMulta] = []
    for tr in rows.find_all("tr"):
        if not tr.find("td", attrs={"data-label": True}):
            continue

        tipo_cell = tr.find("td", attrs={"data-label": "Tipo"})
        numero = None
        tipo = None
        fecha = None

        if tipo_cell:
            link = tipo_cell.find("a", id="verDetalle")
            if link:
                span = link.find("span")
                if span:
                    numero = _clean_text(span.get_text())
            p_tag = tipo_cell.find("p")
            if p_tag:
                tipo = _clean_text(p_tag.get_text())
            for span in tipo_cell.find_all("span"):
                txt = _clean_text(span.get_text())
                if "fecha imposición" in txt.lower():
                    fecha = re.sub(r"(?i)fecha imposición:\s*", "", txt).strip()

        infraccion, infraccion_desc = _parse_infraccion(tr)
        valor_pagar_raw = _cell_by_label(tr, "Valor a pagar")

        result.append(ComparendoMulta(
            numero=numero,
            tipo=tipo,
            fecha_imposicion=fecha,
            notificacion=_cell_by_label(tr, "Notificación"),
            placa=_cell_by_label(tr, "Placa"),
            secretaria=_cell_by_label(tr, "Secretaría"),
            infraccion=infraccion,
            infraccion_descripcion=infraccion_desc,
            estado=_parse_estado(tr),
            valor=_extract_currency(_cell_by_label(tr, "Valor")),
            valor_a_pagar=_extract_currency(valor_pagar_raw),
        ))

    return result


def _extraer_total_desde_label(lab) -> Optional[TotalSeccion]:
    """Extrae total de un <label>: 'Total (N):' o 'Total acuerdos (N):'."""
    txt = _clean_text(lab.get_text())
    match = re.search(r"Total(?:\s+acuerdos)?\s*\((\d+)\)\s*:", txt, re.I)
    if not match:
        return None

    cantidad = int(match.group(1))
    valor = None
    span = lab.find_next_sibling("span")
    if span:
        valor = _extract_currency(span.get_text())
    if not valor and lab.parent:
        bold = lab.parent.find("span", class_=re.compile(r"font-weight-bold"))
        if bold:
            valor = _extract_currency(bold.get_text())
    if not valor:
        resto = txt[match.end():]
        valor = _extract_currency(resto)

    return TotalSeccion(cantidad=cantidad, valor=valor)


def _parse_total_seccion(soup: BeautifulSoup, table_id: str) -> Optional[TotalSeccion]:
    """Parsea 'Total (N):' o 'Total acuerdos (N):' al pie de una tabla."""
    table = soup.find(id=table_id)
    if not table:
        return None

    containers: List = []
    card = table.find_parent("div", class_=re.compile(r"card"))
    if card:
        containers.append(card)
    parent = table.parent
    for _ in range(5):
        if parent is None or parent.name == "body":
            break
        containers.append(parent)
        parent = parent.parent

    vistos: set = set()
    for container in containers:
        cid = id(container)
        if cid in vistos:
            continue
        vistos.add(cid)
        for lab in container.find_all("label"):
            total = _extraer_total_desde_label(lab)
            if total:
                return total

    return None


def _parse_acuerdos_pago(soup: BeautifulSoup) -> List[AcuerdoPago]:
    table = soup.find(id="acuerdoTable")
    if not table:
        for h in soup.find_all(["h5", "h6"]):
            if h and re.search(r"acuerdos de pago", h.get_text(), re.I):
                table = h.find_parent("div", class_=re.compile(r"card"))
                if table:
                    table = table.find("table")
                break

    if not table:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    result: List[AcuerdoPago] = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue

        def cell(label: str) -> Optional[str]:
            td = tr.find("td", attrs={"data-label": label})
            raw = _cell_visible_text(td)
            if label in ("Valor a pagar", "Valor acuerdo", "Pendiente"):
                return _extract_currency(raw)
            return raw

        numero_raw = cell("Número acuerdo") or _clean_text(cells[0].get_text())
        fecha = None
        numero = numero_raw
        if numero_raw and "\n" in numero_raw:
            parts = numero_raw.split("\n")
            numero = _clean_text(parts[0])
            if len(parts) > 1:
                fecha = _clean_text(parts[1])

        result.append(AcuerdoPago(
            numero_acuerdo=numero,
            fecha=fecha,
            secretaria=cell("Secretaría"),
            valor_acuerdo=cell("Valor acuerdo"),
            pendiente=cell("Pendiente"),
            cuota=cell("Cuota"),
            valor_a_pagar=cell("Valor a pagar"),
            descuento=None,
        ))

    return result


def parse_simit_html(
    raw_html: str,
    identificador: str,
    modo: str,
) -> ResultadoSimit:
    soup = BeautifulSoup(raw_html, "html.parser")

    resumen = _parse_resumen(soup, identificador, modo)
    comparendos_multas = _parse_comparendos_multas(soup)
    acuerdos = _parse_acuerdos_pago(soup)
    total_cm = _parse_total_seccion(soup, "multaTable")
    total_ac = _parse_total_seccion(soup, "acuerdoTable")

    tiene_datos = (
        soup.find(id="resumenEstadoCuenta")
        or soup.find(id="multaTable")
        or soup.find(id="acuerdoTable")
        or resumen.mensaje_estado
    )
    # "Sin pendientes" es un resultado válido (vacío), no un fallo ni "sin registro".
    if resumen.sin_pendientes:
        sin_registro = False
    else:
        sin_registro = not bool(tiene_datos)

    return ResultadoSimit(
        resumen=resumen,
        comparendos_multas=comparendos_multas,
        acuerdos_pago=acuerdos,
        total_comparendos_multas=total_cm,
        total_acuerdos_pago=total_ac,
        raw_html=raw_html,
        sin_registro=sin_registro,
        error=None,
        datos_raw={
            "resumen_pairs": _extract_label_strong_pairs(soup.find(id="resumenEstadoCuenta")),
        },
    )
