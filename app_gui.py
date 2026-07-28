# app_gui.py
"""
Punto de entrada de la aplicación de escritorio (GUI) para consulta RUNT.
"""

from utils.logging_setup import setup_logging
from views.gui_qt import run_gui

if __name__ == "__main__":
    setup_logging()
    run_gui()
