# services/runt_parser.py
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any


# -----------------------------
# Helpers: normalización
# -----------------------------
def _clean_text(s: str) -> str:
    return " ".join((s or "").split()).strip()


def _norm_key(s: str) -> str:
    # Clave tipo: "NRO. DOCUMENTO:" -> "NRO. DOCUMENTO"
    return _clean_text(s).replace(":", "").upper()


# -----------------------------
# Helpers: extraer label -> value (layout RUNT: <label> ... <b>)
# -----------------------------
def _extract_label_b_pairs(container) -> Dict[str, Optional[str]]:
    """
    Extrae pares tipo:
      <label>ALGO:</label>  (en un div)
      <b>VALOR</b>          (en el div hermano)

    Esto aplica para:
    - Multas e infracciones (TIENE MULTAS..., NRO. PAZ Y SALVO)
    - Validación (INDICADOR DE ESTADO CIUDADANO, FECHA DESBLOQUEO, etc.)
    - Bloques superiores de info personal (según cómo venga el DOM)
    """
    data: Dict[str, Optional[str]] = {}
    labels = container.find_all("label")
    for lab in labels:
        key = _norm_key(lab.get_text(" ", strip=True))
        if not key:
            continue

        # 1) Caso típico: label dentro de un div "col-...", y el valor está en el siguiente div hermano
        label_col = lab.find_parent("div")
        value = None

        if label_col:
            sib = label_col.find_next_sibling("div")
            if sib:
                val_tag = sib.find(["b", "span"])
                if val_tag:
                    value = _clean_text(val_tag.get_text(" ", strip=True))
                else:
                    value = _clean_text(sib.get_text(" ", strip=True))

        # 2) Fallback: buscar el siguiente <b> cercano después del label
        if not value:
            b = lab.find_next("b")
            if b:
                value = _clean_text(b.get_text(" ", strip=True))

        data[key] = value if value else None

    # Limpieza: si todo quedó None, devolver {}
    if all(v is None for v in data.values()):
        return {}
    return data


# -----------------------------
# Helpers: cards (si alguna sección usa mat-card)
# -----------------------------
def _extract_label_strong_pairs(container) -> Dict[str, Optional[str]]:
    """
    Soporta layouts tipo:
      <strong>LABEL:</strong> valor
    """
    data: Dict[str, Optional[str]] = {}
    for tag in container.find_all(["p", "div"], recursive=True):
        strong = tag.find("strong")
        if not strong:
            continue
        label = _norm_key(strong.get_text(" ", strip=True))
        strong.extract()
        value_text = _clean_text(tag.get_text(" ", strip=True))
        data[label] = value_text if value_text else None
    if all(v is None for v in data.values()):
        return {}
    return data


def _parse_cards_as_list(body) -> List[Dict[str, Optional[str]]]:
    records: List[Dict[str, Optional[str]]] = []
    cards = body.select("mat-card, .card")
    for card in cards:
        content = card.find("mat-card-content") or card
        card_data = _extract_label_strong_pairs(content) or _extract_label_b_pairs(content)
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
    headers = [ _norm_key(th.get_text(" ", strip=True)) for th in table.find_all("th") ]
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
        cells = [_clean_text(td.get_text(" ", strip=True)) for td in tds]

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
    personal_data = _extract_label_b_pairs(soup)

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
        partes = _clean_text(documento_raw).split()
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
        titulo = _norm_key(title_el.get_text(" ", strip=True))

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
        lb = _extract_label_b_pairs(body)
        if lb:
            secciones[titulo] = lb
            continue

        # 2.3) Cards (PRIORIDAD 3)
        cards = _parse_cards_as_list(body)
        if cards:
            secciones[titulo] = cards
            continue

        # 2.4) Strong pairs (PRIORIDAD 4)
        strong_pairs = _extract_label_strong_pairs(body)
        if strong_pairs:
            secciones[titulo] = strong_pairs
            continue

        # 2.5) Fallback texto
        texto = _clean_text(body.get_text(" ", strip=True))
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
