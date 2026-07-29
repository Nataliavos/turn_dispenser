"""Tests ligeros de helpers compartidos (C-03)."""

from __future__ import annotations

from bs4 import BeautifulSoup

from services.parse_helpers import (
    clean_text,
    extract_label_b_pairs,
    extract_label_with_strong_value_pairs,
    extract_strong_as_label_pairs,
    norm_key,
)


def test_clean_text_and_norm_key() -> None:
    assert clean_text("  hola   mundo  ") == "hola mundo"
    assert norm_key("Nro. Documento:") == "NRO. DOCUMENTO"


def test_extract_label_b_pairs_runt_layout() -> None:
    html = """
    <div class="row">
      <div class="col"><label>NOMBRE:</label></div>
      <div class="col"><b>ANA PRUEBA</b></div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert extract_label_b_pairs(soup)["NOMBRE"] == "ANA PRUEBA"


def test_extract_label_with_strong_value_simit_layout() -> None:
    html = """
    <div>
      <label>Comparendos:</label>
      <strong>2</strong>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert extract_label_with_strong_value_pairs(soup)["COMPARENDOS"] == "2"


def test_extract_strong_as_label_pairs() -> None:
    html = """
    <div><strong>ESTADO:</strong> ACTIVO</div>
    """
    soup = BeautifulSoup(html, "html.parser")
    assert extract_strong_as_label_pairs(soup)["ESTADO"] == "ACTIVO"
