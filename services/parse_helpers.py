"""
Helpers compartidos de parseo HTML (BeautifulSoup) para RUNT / SIMIT.

Ticket C-03: limpieza de texto y extracción label/valor reutilizable.

Nota: RUNT y SIMIT usan layouts distintos para ``label``/``strong``;
por eso hay dos extractores de pares strong (no fusionar semánticas).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def clean_text(s: Optional[str]) -> str:
    """Normaliza espacios en blanco de un texto."""
    return " ".join((s or "").split()).strip()


def norm_key(s: Optional[str]) -> str:
    """Clave de etiqueta: ``NRO. DOCUMENTO:`` → ``NRO. DOCUMENTO``."""
    return clean_text(s).replace(":", "").upper()


def extract_label_b_pairs(container: Any) -> Dict[str, Optional[str]]:
    """
    Extrae pares ``<label>…</label>`` + valor en ``<b>`` / hermano (layout RUNT).

    Caso típico: label en un ``div`` columna y valor en el ``div`` hermano.
    """
    if container is None:
        return {}

    data: Dict[str, Optional[str]] = {}
    labels = container.find_all("label")
    for lab in labels:
        key = norm_key(lab.get_text(" ", strip=True))
        if not key:
            continue

        label_col = lab.find_parent("div")
        value = None

        if label_col:
            sib = label_col.find_next_sibling("div")
            if sib:
                val_tag = sib.find(["b", "span"])
                if val_tag:
                    value = clean_text(val_tag.get_text(" ", strip=True))
                else:
                    value = clean_text(sib.get_text(" ", strip=True))

        if not value:
            b = lab.find_next("b")
            if b:
                value = clean_text(b.get_text(" ", strip=True))

        data[key] = value if value else None

    if not data or all(v is None for v in data.values()):
        return {}
    return data


def extract_strong_as_label_pairs(container: Any) -> Dict[str, Optional[str]]:
    """
    Layout tipo RUNT cards: ``<strong>LABEL:</strong> valor`` en el mismo nodo.
    """
    if container is None:
        return {}

    data: Dict[str, Optional[str]] = {}
    for tag in container.find_all(["p", "div"], recursive=True):
        strong = tag.find("strong")
        if not strong:
            continue
        label = norm_key(strong.get_text(" ", strip=True))
        strong.extract()
        value_text = clean_text(tag.get_text(" ", strip=True))
        data[label] = value_text if value_text else None

    if not data or all(v is None for v in data.values()):
        return {}
    return data


def extract_label_with_strong_value_pairs(
    container: Any,
) -> Dict[str, Optional[str]]:
    """
    Layout tipo SIMIT resumen: ``<label>KEY:</label>`` + ``<strong>valor</strong>``.
    """
    data: Dict[str, Optional[str]] = {}
    if container is None:
        return data

    for lab in container.find_all("label"):
        key = norm_key(lab.get_text(" ", strip=True))
        if not key:
            continue

        value = None
        parent = lab.parent
        if parent:
            strong = parent.find("strong")
            if strong:
                value = clean_text(strong.get_text(" ", strip=True))
            else:
                sib = parent.find_next_sibling()
                if sib:
                    strong = sib.find("strong")
                    value = clean_text((strong or sib).get_text(" ", strip=True))

        if not value:
            nxt = lab.find_next("strong")
            if nxt:
                value = clean_text(nxt.get_text(" ", strip=True))

        data[key] = value if value else None

    return data
