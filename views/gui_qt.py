# views/gui_qt.py
"""
Vista gráfica (GUI) para consulta RUNT + SIMIT usando PyQt6 + QThread.

- Modo DOCUMENTO: consulta paralela RUNT + SIMIT.
- Modo PLACA: consulta solo SIMIT.
- CAPTCHA RUNT resuelto manualmente vía diálogo.
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
    QButtonGroup,
    QRadioButton,
    QStackedWidget,
)
from PyQt6.QtGui import QPixmap, QRegularExpressionValidator
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QEventLoop, QRegularExpression

from config.settings import get_settings
from controllers.consulta_controller import ConsultaController
from models.consulta_models import ConsultaParams
from utils.documento_validator import validar_documento
from utils.placa_validator import es_placa_valida, normalizar_placa, MENSAJE_PLACA_INVALIDA
from views.resultado_formatter import (
    formatear_resultado_consulta,
    resumen_estados_consulta,
)


# ------------------------------------------------------------
# Diálogo para mostrar la imagen del CAPTCHA y pedir el texto
# ------------------------------------------------------------
class CaptchaDialog(QDialog):
    def __init__(self, image_bytes: bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resolver CAPTCHA (RUNT)")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        pixmap = QPixmap()
        pixmap.loadFromData(image_bytes)

        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Digite el texto del CAPTCHA…")
        layout.addWidget(self._edit)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def captcha_text(self) -> str:
        return self._edit.text().strip()


# ------------------------------------------------------------
# Worker que corre la consulta en segundo plano
# ------------------------------------------------------------
class ConsultaWorker(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    log = pyqtSignal(str)
    captchaRequested = pyqtSignal(bytes)
    _captchaResolved = pyqtSignal(str)

    def __init__(self, params: ConsultaParams, debug: bool = True, parent=None):
        super().__init__(parent)
        self.params = params
        self.debug = debug
        self.controller = ConsultaController()
        self._captcha_loop: QEventLoop | None = None
        self._captcha_text: str = ""
        self._captchaResolved.connect(self._on_captcha_resolved)

    @pyqtSlot()
    def run(self):
        try:
            if self.params.modo == "DOCUMENTO":
                self.log.emit(
                    f"Iniciando consulta paralela RUNT + SIMIT "
                    f"(tipo={self.params.tipo_documento}, id={self.params.identificador})"
                )
            else:
                self.log.emit(
                    f"Iniciando consulta SIMIT por placa: {self.params.identificador}"
                )

            resultado = self.controller.consultar(
                params=self.params,
                resolver_captcha=self._resolver_captcha_desde_worker,
                debug=self.debug,
            )
            self.finished.emit(resultado)

        except Exception as e:
            self.error.emit(str(e))

    def _resolver_captcha_desde_worker(self, image_bytes: bytes) -> str:
        self.captchaRequested.emit(image_bytes)
        loop = QEventLoop()
        self._captcha_loop = loop
        loop.exec()
        return self._captcha_text

    @pyqtSlot(str)
    def _on_captcha_resolved(self, text: str):
        self._captcha_text = text
        if self._captcha_loop is not None:
            self._captcha_loop.quit()
            self._captcha_loop = None


# ------------------------------------------------------------
# Ventana principal
# ------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Turn Dispenser — Consulta RUNT + SIMIT")
        self.setMinimumSize(720, 480)

        self._thread: QThread | None = None
        self._worker: ConsultaWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ---- Modo de consulta ----
        fila_modo = QHBoxLayout()
        fila_modo.addWidget(QLabel("Consultar por:"))

        self.grp_modo = QButtonGroup(self)
        self.rb_documento = QRadioButton("Documento de identidad")
        self.rb_placa = QRadioButton("Placa del vehículo")
        self.rb_documento.setChecked(True)

        self.grp_modo.addButton(self.rb_documento, 0)
        self.grp_modo.addButton(self.rb_placa, 1)

        fila_modo.addWidget(self.rb_documento)
        fila_modo.addWidget(self.rb_placa)
        fila_modo.addStretch()
        main_layout.addLayout(fila_modo)

        # ---- Campos según modo ----
        self.stack_campos = QStackedWidget()

        # Página 0: documento
        pagina_doc = QWidget()
        layout_doc = QHBoxLayout(pagina_doc)

        lbl_tipo = QLabel("Tipo de documento:")
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem("Cédula de Ciudadanía (CC)", userData="CC")
        self.cmb_tipo.addItem("Cédula de Extranjería (CE)", userData="CE")
        self.cmb_tipo.addItem("Tarjeta de Identidad (TI)", userData="TI")
        self.cmb_tipo.addItem("Registro Civil (RC)", userData="RC")
        self.cmb_tipo.addItem("Permiso por Protección Temporal (PPT)", userData="PPT")
        self.cmb_tipo.addItem("Pasaporte (PA)", userData="PA")
        self.cmb_tipo.addItem("Carnet Diplomático (CD)", userData="CD")

        lbl_numero = QLabel("Número de documento:")
        self.txt_documento = QLineEdit()
        self.txt_documento.setPlaceholderText("Ejemplo: 1017259440")

        layout_doc.addWidget(lbl_tipo)
        layout_doc.addWidget(self.cmb_tipo, stretch=1)
        layout_doc.addSpacing(16)
        layout_doc.addWidget(lbl_numero)
        layout_doc.addWidget(self.txt_documento, stretch=1)

        # Página 1: placa
        pagina_placa = QWidget()
        layout_placa = QHBoxLayout(pagina_placa)

        lbl_placa = QLabel("Placa del vehículo:")
        self.txt_placa = QLineEdit()
        self.txt_placa.setPlaceholderText("Ejemplo: ABC123, ABC12D, R12345")
        self.txt_placa.setMaxLength(6)
        self.txt_placa.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^[A-Za-z0-9]{0,6}$"))
        )

        layout_placa.addWidget(lbl_placa)
        layout_placa.addWidget(self.txt_placa, stretch=1)

        self.stack_campos.addWidget(pagina_doc)
        self.stack_campos.addWidget(pagina_placa)
        main_layout.addWidget(self.stack_campos)

        self.rb_documento.toggled.connect(self._on_modo_changed)

        # ---- Botón consulta ----
        self.btn_consultar = QPushButton("Consultar")
        self.btn_consultar.clicked.connect(self.on_consultar_clicked)
        main_layout.addWidget(self.btn_consultar)

        # ---- Estado + log ----
        self.lbl_estado = QLabel("Listo para consultar.")
        main_layout.addWidget(self.lbl_estado)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        main_layout.addWidget(self.txt_log, stretch=1)

    def _on_modo_changed(self, checked: bool):
        if self.rb_documento.isChecked():
            self.stack_campos.setCurrentIndex(0)
        else:
            self.stack_campos.setCurrentIndex(1)

    def log(self, mensaje: str):
        self.txt_log.append(f"➡ {mensaje}")

    def on_consultar_clicked(self):
        if self.rb_documento.isChecked():
            modo = "DOCUMENTO"
            tipo_raw = self.cmb_tipo.currentData() or ""
            numero_raw = self.txt_documento.text()
            ok, tipo_doc, identificador, msg = validar_documento(tipo_raw, numero_raw)
            if not ok:
                QMessageBox.warning(self, "Documento inválido", msg)
                return
        else:
            modo = "PLACA"
            identificador = normalizar_placa(self.txt_placa.text())
            tipo_doc = None
            if not identificador:
                QMessageBox.warning(self, "Dato requerido", "Debes ingresar la placa del vehículo.")
                return
            if not es_placa_valida(identificador):
                QMessageBox.warning(self, "Placa inválida", MENSAJE_PLACA_INVALIDA)
                return

        params = ConsultaParams(
            modo=modo,
            identificador=identificador,
            tipo_documento=tipo_doc,
        )

        self.btn_consultar.setEnabled(False)
        if modo == "DOCUMENTO":
            self.lbl_estado.setText("Consultando en RUNT y SIMIT en paralelo…")
            self.log(f"Iniciando consulta documento: tipo={tipo_doc}, número={identificador}")
        else:
            self.lbl_estado.setText("Consultando en SIMIT por placa…")
            self.log(f"Iniciando consulta placa: {identificador}")

        self._thread = QThread(self)
        self._worker = ConsultaWorker(params=params, debug=get_settings().debug)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.log.connect(self._on_worker_log)
        self._worker.captchaRequested.connect(self._on_captcha_requested)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    @pyqtSlot(str)
    def _on_worker_log(self, msg: str):
        self.log(msg)

    @pyqtSlot(object)
    def _on_worker_finished(self, resultado):
        self.lbl_estado.setText(resumen_estados_consulta(resultado))
        self.log("✅ Consulta finalizada.")
        formatear_resultado_consulta(resultado, self.log)
        if resultado.error_persistencia:
            QMessageBox.warning(
                self,
                "No se guardó en la base de datos",
                "La consulta se completó y los resultados se muestran aquí,\n"
                "pero no se pudieron guardar en Supabase/Postgres.\n\n"
                f"{resultado.error_persistencia}",
            )
        self.btn_consultar.setEnabled(True)

    @pyqtSlot(str)
    def _on_worker_error(self, error_msg: str):
        self.lbl_estado.setText("Error durante la consulta.")
        self.log(f"Error: {error_msg}")
        QMessageBox.critical(self, "Error en la consulta", f"Ocurrió un error:\n{error_msg}")
        self.btn_consultar.setEnabled(True)

    @pyqtSlot(bytes)
    def _on_captcha_requested(self, image_bytes: bytes):
        dlg = CaptchaDialog(image_bytes, parent=self)
        result = dlg.exec()
        text = dlg.captcha_text() if result == QDialog.DialogCode.Accepted else ""
        if self._worker is not None:
            self._worker._captchaResolved.emit(text)


def run_gui():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
