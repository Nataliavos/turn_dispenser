# services/runt_parser.py
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from services.parse_helpers import (
    clean_text,
    extract_label_b_pairs,
    extract_strong_as_label_pairs,
    norm_key,
)


def _parse_cards_as_list(body) -> List[Dict[str, Optional[str]]]:
    records: List[Dict[str, Optional[str]]] = []
    cards = body.select("mat-card, .card")
    for card in cards:
        content = card.find("mat-card-content") or card
        card_data = extract_strong_as_label_pairs(content) or extract_label_b_pairs(
            content
        )
        if card_data:
            records.append(card_data)
    return records


# -----------------------------
# Helpers: parse mat-table
# -----------------------------
def _parse_mat_table(table) -> Optional[List[Dict[str, Optional[str]]]]:
    """
    Parsea tablas Angular Material (mat-table).
    Estructura típica:
      <thead> <th>...</th> </thead>
      <tbody> <tr> <td>...</td> </tr> ... </tbody>

    Devuelve lista de dicts por fila. Si no hay filas, devuelve None.
    """
    # Headers: usa th del thead o el primer header-row
    headers = [norm_key(th.get_text(" ", strip=True)) for th in table.find_all("th")]
    headers = [h for h in headers if h]  # filtra vacíos

    tbody = table.find("tbody")
    if not tbody:
        return None

    rows = tbody.find_all("tr")
    if not rows:
        return None

    out: List[Dict[str, Optional[str]]] = []
    for tr in rows:
        tds = tr.find_all("td")
        if not tds:
            continue
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tds]

        # Mapea por headers si coinciden; si no, usa COL_1, COL_2...
        if headers and len(headers) >= 1:
            row = {}
            for i, cell in enumerate(cells):
                key = headers[i] if i < len(headers) else f"COL_{i+1}"
                row[key] = cell if cell else None
            out.append(row)
        else:
            row = {f"COL_{i+1}": (cells[i] if cells[i] else None) for i in range(len(cells))}
            out.append(row)

    return out or None


def _parse_any_tables(body) -> Optional[List[Dict[str, Optional[str]]]]:
    """
    Busca cualquier table dentro del body y parsea la primera que tenga filas.
    Algunas secciones pueden tener más de una tabla, entonces probamos en orden.
    """
    for table in body.find_all("table"):
        parsed = _parse_mat_table(table)
        if parsed:
            return parsed
    return None


# -----------------------------
# Parser principal
# -----------------------------
def parse_runt_html(raw_html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(raw_html, "html.parser")

    # --- 1) Datos personales (robusto)
    # En RUNT aparecen como <label> ... y el valor al lado en <b>
    personal_data = extract_label_b_pairs(soup)

    # Claves que esperas (pueden variar, así que guardamos por si vienen diferente)
    nombre = personal_data.get("NOMBRE COMPLETO") or personal_data.get("NOMBRE")
    documento_raw = personal_data.get("DOCUMENTO")
    estado_persona = personal_data.get("ESTADO DE LA PERSONA")
    estado_conductor = personal_data.get("ESTADO DEL CONDUCTOR")
    numero_inscripcion = personal_data.get("NÚMERO DE INSCRIPCIÓN") or personal_data.get("NUMERO DE INSCRIPCION")
    fecha_inscripcion = personal_data.get("FECHA DE INSCRIPCIÓN") or personal_data.get("FECHA DE INSCRIPCION")

    tipo_doc = None
    num_doc = None
    if documento_raw:
        partes = clean_text(documento_raw).split()
        if len(partes) >= 2:
            tipo_doc = partes[0].replace(".", "")
            num_doc = partes[-1]

    # --- 2) Secciones (mat-expansion-panel)
    secciones: Dict[str, Any] = {}
    panels = soup.find_all("mat-expansion-panel")
    for panel in panels:
        title_el = panel.find("span", class_="panel-title-text")
        if not title_el:
            continue
        titulo = norm_key(title_el.get_text(" ", strip=True))

        body = panel.find("div", class_="mat-expansion-panel-body")
        if not body:
            secciones[titulo] = None
            continue

        # 2.1) Si hay tablas con filas: parsear (PRIORIDAD 1)
        table_rows = _parse_any_tables(body)
        if table_rows:
            secciones[titulo] = table_rows
            continue

        # 2.2) Si no hay filas, pero es sección tipo form/labels: parsear label/b (PRIORIDAD 2)
        lb = extract_label_b_pairs(body)
        if lb:
            secciones[titulo] = lb
            continue

        # 2.3) Cards (PRIORIDAD 3)
        cards = _parse_cards_as_list(body)
        if cards:
            secciones[titulo] = cards
            continue

        # 2.4) Strong pairs (PRIORIDAD 4)
        strong_pairs = extract_strong_as_label_pairs(body)
        if strong_pairs:
            secciones[titulo] = strong_pairs
            continue

        # 2.5) Fallback texto
        texto = clean_text(body.get_text(" ", strip=True))
        if texto:
            # Limpieza ligera: si solo quedan headers sin datos, puede parecer “contenido”
            # pero no lo matamos aquí porque a veces es lo único disponible.
            secciones[titulo] = texto
        else:
            secciones[titulo] = None

    return {
        "nombre_completo": nombre,
        "tipo_documento": tipo_doc,
        "numero_documento": num_doc,
        "estado_persona": estado_persona,
        "estado_conductor": estado_conductor,
        "numero_inscripcion": numero_inscripcion,
        "fecha_inscripcion": fecha_inscripcion,
        "secciones": secciones,
        "personal_raw": personal_data,  # útil para debug (puedes quitarlo luego)
    }
