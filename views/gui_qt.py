# views/gui_qt.py
"""
Vista gráfica (GUI) para la consulta al RUNT usando PyQt6 + QThread.

- Ventana principal: formulario + logs.
- Worker en segundo plano corre Playwright (run_runt_flow).
- Cuando el worker necesita resolver un CAPTCHA, emite una señal
  que la GUI atiende mostrando un diálogo con la imagen.
"""

import sys

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTextEdit,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QEventLoop

from controllers.runt_controller import RuntController
from models.runt_models import ConsultaRuntParams


# ------------------------------------------------------------
# Diálogo para mostrar la imagen del CAPTCHA y pedir el texto
# ------------------------------------------------------------
class CaptchaDialog(QDialog):
    def __init__(self, image_bytes: bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resolver CAPTCHA")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        # Imagen del captcha
        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)

        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        # Campo de texto para ingresar el captcha
        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Digite el texto del CAPTCHA…")
        layout.addWidget(self._edit)

        # Botones OK / Cancelar
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def captcha_text(self) -> str:
        return self._edit.text().strip()


# ------------------------------------------------------------
# Worker que corre la consulta en segundo plano (otro hilo)
# ------------------------------------------------------------
class RuntWorker(QObject):
    finished = pyqtSignal(object)         # ResultadoRunt
    error = pyqtSignal(str)               # Mensaje de error
    log = pyqtSignal(str)                 # Mensajes de log para la GUI
    captchaRequested = pyqtSignal(bytes)  # Pide al hilo de GUI mostrar captcha
    _captchaResolved = pyqtSignal(str)    # GUI responde con el texto

    def __init__(self, params: ConsultaRuntParams, debug: bool = True, parent=None):
        super().__init__(parent)
        self.params = params
        self.debug = debug
        self.controller = RuntController()

        self._captcha_loop: QEventLoop | None = None
        self._captcha_text: str = ""

        # Conectamos la señal interna que la GUI emitirá cuando tenga el texto de captcha
        self._captchaResolved.connect(self._on_captcha_resolved)

    @pyqtSlot()
    def run(self):
        """Método que se ejecuta en el hilo secundario."""
        try:
            self.log.emit(
                f"Iniciando consulta en worker para tipo={self.params.tipo_documento}, "
                f"número={self.params.numero_documento}"
            )

            resultado = self.controller.consultar_ciudadano(
                params=self.params,
                resolver_captcha=self._resolver_captcha_desde_worker,
                debug=self.debug,
            )

            self.finished.emit(resultado)

        except Exception as e:
            self.error.emit(str(e))

    # --------------------------------------------------------
    # Manejo del CAPTCHA desde el worker
    # --------------------------------------------------------
    def _resolver_captcha_desde_worker(self, image_bytes: bytes) -> str:
        """
        Este método lo llama el servicio Playwright (en este mismo hilo).
        Aquí no podemos abrir diálogos de Qt directamente, así que:
        - Emitimos una señal captchaRequested(image_bytes) para que la GUI lo muestre.
        - Creamos un QEventLoop local que bloquea SOLO este hilo hasta que
          la GUI nos responda con el texto vía la señal _captchaResolved(str).
        """
        # Pedimos a la GUI que muestre el diálogo
        self.captchaRequested.emit(image_bytes)

        # Creamos un loop para esperar la respuesta
        loop = QEventLoop()
        self._captcha_loop = loop
        loop.exec()  # se queda bloqueado este hilo hasta que _on_captcha_resolved haga loop.quit()

        # Devolvemos el texto del captcha al flujo de Playwright
        return self._captcha_text

    @pyqtSlot(str)
    def _on_captcha_resolved(self, text: str):
        """
        Slot que recibe el texto del CAPTCHA desde la GUI.
        Cierra el loop interno para que _resolver_captcha_desde_worker continúe.
        """
        self._captcha_text = text
        if self._captcha_loop is not None:
            self._captcha_loop.quit()
            self._captcha_loop = None


# ------------------------------------------------------------
# Ventana principal de la aplicación
# ------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Consulta RUNT - Turn Dispenser")
        self.setMinimumSize(640, 320)

        # Referencias al hilo/worker actuales (para no perderlos)
        self._thread: QThread | None = None
        self._worker: RuntWorker | None = None

        # ---- Layout principal ----
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ---- Fila de tipo de documento y número ----
        fila_doc = QHBoxLayout()

        lbl_tipo = QLabel("Tipo de documento:")
        self.cmb_tipo = QComboBox()
        # Texto visible + código que se envía al servicio
        self.cmb_tipo.addItem("Cédula de Ciudadanía (CC)", userData="CC")
        self.cmb_tipo.addItem("Cédula de Extranjería (CE)", userData="CE")
        self.cmb_tipo.addItem("Tarjeta de Identidad (TI)", userData="TI")
        self.cmb_tipo.addItem("Registro Civil (RC)", userData="RC")
        self.cmb_tipo.addItem("Permiso por Protección Temporal (PPT)", userData="PPT")

        lbl_numero = QLabel("Número de documento:")
        self.txt_numero = QLineEdit()
        self.txt_numero.setPlaceholderText("Ejemplo: 1017259440")

        fila_doc.addWidget(lbl_tipo)
        fila_doc.addWidget(self.cmb_tipo, stretch=1)
        fila_doc.addSpacing(16)
        fila_doc.addWidget(lbl_numero)
        fila_doc.addWidget(self.txt_numero, stretch=1)

        main_layout.addLayout(fila_doc)

        # ---- Botón de consulta ----
        self.btn_consultar = QPushButton("Consultar en RUNT")
        self.btn_consultar.clicked.connect(self.on_consultar_clicked)
        main_layout.addWidget(self.btn_consultar)

        # ---- Área de estado + log ----
        self.lbl_estado = QLabel("Listo para consultar.")
        main_layout.addWidget(self.lbl_estado)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        main_layout.addWidget(self.txt_log, stretch=1)

    # --------------------------------------------------------
    # Helpers de la vista
    # --------------------------------------------------------
    def log(self, mensaje: str):
        """Agrega un mensaje al área de log."""
        self.txt_log.append(f"➡ {mensaje}")

    # --------------------------------------------------------
    # Slot: clic en el botón "Consultar en RUNT"
    # --------------------------------------------------------
    def on_consultar_clicked(self):
        tipo_codigo = self.cmb_tipo.currentData()
        numero = self.txt_numero.text().strip()

        if not numero:
            QMessageBox.warning(self, "Dato requerido", "Debes ingresar el número de documento.")
            return

        params = ConsultaRuntParams(
            tipo_documento=tipo_codigo,
            numero_documento=numero,
        )

        # Preparamos estado de UI
        self.btn_consultar.setEnabled(False)
        self.lbl_estado.setText("Consultando en el portal del RUNT…")
        self.log(f"Iniciando consulta para tipo={tipo_codigo}, número={numero}")

        # Creamos hilo y worker
        self._thread = QThread(self)
        self._worker = RuntWorker(params=params, debug=True)
        self._worker.moveToThread(self._thread)

        # Conexiones: inicio y fin del hilo
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.log.connect(self._on_worker_log)
        self._worker.captchaRequested.connect(self._on_captcha_requested)

        # Limpieza cuando termina
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.error.connect(self._thread.quit)

        # Iniciar el hilo
        self._thread.start()

    # --------------------------------------------------------
    # Slots que reciben señales del worker
    # --------------------------------------------------------
    @pyqtSlot(str)
    def _on_worker_log(self, msg: str):
        self.log(msg)

    @pyqtSlot(object)
    def _on_worker_finished(self, resultado):
        sin_registro = getattr(resultado, "sin_registro", False)

        if sin_registro:
            msg = "La persona no tiene registro ACTIVO en RUNT (o está SIN REGISTRO)."
            self.lbl_estado.setText(msg)
            self.log(msg)
            QMessageBox.information(self, "Sin registro", msg)
            self.btn_consultar.setEnabled(True)
            return

        # ✅ Resumen
        self.lbl_estado.setText("Consulta completada.")
        self.log("✅ Consulta completada.")
        self.log(f"Nombre: {resultado.nombre}")
        self.log(f"Estado conductor: {resultado.estado_licencia}")
        self.log(f"Tiene multas: {resultado.tiene_multas}")

        # ✅ Secciones (vista inicial: texto)
        secciones = getattr(resultado, "secciones", {}) or {}
        if not secciones:
            self.log("ℹ No se detectaron secciones en el resultado parseado.")
        else:
            for titulo, contenido in secciones.items():
                self.log(f"\n=== {titulo} ===")

                if contenido is None:
                    self.log("Sin información.")
                elif isinstance(contenido, list):
                    for i, item in enumerate(contenido, start=1):
                        self.log(f"--- Registro #{i} ---")
                        if isinstance(item, dict):
                            for k, v in item.items():
                                self.log(f"{k}: {v}")
                        else:
                            self.log(str(item))
                elif isinstance(contenido, dict):
                    for k, v in contenido.items():
                        self.log(f"{k}: {v}")
                else:
                    self.log(str(contenido))

        self.btn_consultar.setEnabled(True)


    @pyqtSlot(str)
    def _on_worker_error(self, error_msg: str):
        self.lbl_estado.setText("Error durante la consulta.")
        self.log(f"Error en worker: {error_msg}")
        QMessageBox.critical(self, "Error en la consulta", f"Ocurrió un error:\n{error_msg}")
        self.btn_consultar.setEnabled(True)

    @pyqtSlot(bytes)
    def _on_captcha_requested(self, image_bytes: bytes):
        """
        Este slot corre en el hilo de la GUI.
        Muestra el diálogo del CAPTCHA y responde al worker.
        """
        dlg = CaptchaDialog(image_bytes, parent=self)
        result = dlg.exec()

        if result == QDialog.DialogCode.Accepted:
            text = dlg.captcha_text()
        else:
            text = ""  # usuario canceló

        # Enviamos el texto de vuelta al worker
        if self._worker is not None:
            self._worker._captchaResolved.emit(text)


# ------------------------------------------------------------
# Punto de entrada de la GUI (para app_gui.py)
# ------------------------------------------------------------
def run_gui():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
