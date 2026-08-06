# views/gui_qt.py
"""
Vista gráfica (GUI) para consulta RUNT + SIMIT usando PyQt6 + QThread.

- Modo DOCUMENTO: consulta paralela RUNT + SIMIT.
- Modo PLACA: consulta solo SIMIT.
- CAPTCHA RUNT resuelto manualmente vía diálogo.
- Reintento de consulta completa tras error/parcial (E-01).
- Nueva consulta / Limpiar: resetea estado de sesión en pantalla sin borrar BD (F-03).

Limitación (E-01): no hay reintento por fuente individual. RUNT exige CAPTCHA
manual en el flujo Qt y la orquestación lanza RUNT+SIMIT juntos; mezclar
resultados parciales sería frágil. El operador usa «Reintentar consulta».
"""

import sys
from typing import Optional

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
    etiqueta_estado,
    formatear_resultado_consulta,
    mensajes_recuperacion,
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
    progreso = pyqtSignal(str, str)  # fuente, estado
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
                on_progreso=self._emitir_progreso,
            )
            self.finished.emit(resultado)

        except Exception as e:
            self.error.emit(str(e))

    def _emitir_progreso(self, fuente: str, estado: str) -> None:
        self.progreso.emit(fuente, estado)

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
        self.setMinimumSize(720, 520)

        self._thread: QThread | None = None
        self._worker: ConsultaWorker | None = None
        self._ultimos_params: Optional[ConsultaParams] = None

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

        # ---- Botones consulta / reintento / nueva consulta ----
        fila_botones = QHBoxLayout()
        self.btn_consultar = QPushButton("Consultar")
        self.btn_consultar.clicked.connect(self.on_consultar_clicked)
        fila_botones.addWidget(self.btn_consultar)

        self.btn_reintentar = QPushButton("Reintentar consulta")
        self.btn_reintentar.setEnabled(False)
        self.btn_reintentar.setToolTip(
            "Repite la última consulta completa (RUNT+SIMIT o solo SIMIT).\n"
            "No hay reintento por fuente: RUNT requiere CAPTCHA manual en Qt "
            "y ambas fuentes se lanzan juntas."
        )
        self.btn_reintentar.clicked.connect(self.on_reintentar_clicked)
        fila_botones.addWidget(self.btn_reintentar)

        self.btn_nueva_consulta = QPushButton("Nueva consulta")
        self.btn_nueva_consulta.setToolTip(
            "Limpia formulario, estados y resultados en pantalla para el "
            "siguiente ciudadano.\nNo borra el historial en la base de datos."
        )
        self.btn_nueva_consulta.clicked.connect(self.on_nueva_consulta_clicked)
        fila_botones.addWidget(self.btn_nueva_consulta)
        fila_botones.addStretch()
        main_layout.addLayout(fila_botones)

        # ---- Progreso por fuente (RF-17) ----
        fila_progreso = QHBoxLayout()
        self.lbl_progreso_runt = QLabel("RUNT: —")
        self.lbl_progreso_simit = QLabel("SIMIT: —")
        fila_progreso.addWidget(self.lbl_progreso_runt)
        fila_progreso.addSpacing(24)
        fila_progreso.addWidget(self.lbl_progreso_simit)
        fila_progreso.addStretch()
        main_layout.addLayout(fila_progreso)

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

    def _set_progreso_fuente(self, fuente: str, estado: str) -> None:
        texto = f"{fuente}: {etiqueta_estado(estado)}"
        if fuente.upper() == "RUNT":
            self.lbl_progreso_runt.setText(texto)
        elif fuente.upper() == "SIMIT":
            self.lbl_progreso_simit.setText(texto)

    def _set_controles_consulta_activos(self, activos: bool) -> None:
        self.btn_consultar.setEnabled(activos)
        self.btn_reintentar.setEnabled(activos and self._ultimos_params is not None)
        self.btn_nueva_consulta.setEnabled(activos)
        self.rb_documento.setEnabled(activos)
        self.rb_placa.setEnabled(activos)
        self.cmb_tipo.setEnabled(activos)
        self.txt_documento.setEnabled(activos)
        self.txt_placa.setEnabled(activos)

    def on_consultar_clicked(self):
        params = self._leer_params_desde_formulario()
        if params is None:
            return
        self._iniciar_consulta(params)

    def on_reintentar_clicked(self):
        if self._ultimos_params is None:
            QMessageBox.information(
                self,
                "Sin consulta previa",
                "Aún no hay una consulta para reintentar. Use «Consultar» primero.",
            )
            return
        self.log("— Reintento de consulta completa —")
        self._iniciar_consulta(self._ultimos_params)

    def on_nueva_consulta_clicked(self) -> None:
        """Resetea estado de sesión en UI. No elimina filas en BD."""
        self._ultimos_params = None
        self.txt_documento.clear()
        self.txt_placa.clear()
        self.cmb_tipo.setCurrentIndex(0)
        self.rb_documento.setChecked(True)
        self.stack_campos.setCurrentIndex(0)

        self.lbl_progreso_runt.setText("RUNT: —")
        self.lbl_progreso_simit.setText("SIMIT: —")
        self.lbl_estado.setText("Listo para consultar.")
        self.txt_log.clear()

        self._set_controles_consulta_activos(True)
        self.txt_documento.setFocus()
        self.log("Sesión limpia — lista para nueva consulta (historial BD intacto).")

    def _leer_params_desde_formulario(self) -> Optional[ConsultaParams]:
        if self.rb_documento.isChecked():
            modo = "DOCUMENTO"
            tipo_raw = self.cmb_tipo.currentData() or ""
            numero_raw = self.txt_documento.text()
            ok, tipo_doc, identificador, msg = validar_documento(tipo_raw, numero_raw)
            if not ok:
                QMessageBox.warning(self, "Documento inválido", msg)
                return None
        else:
            modo = "PLACA"
            identificador = normalizar_placa(self.txt_placa.text())
            tipo_doc = None
            if not identificador:
                QMessageBox.warning(
                    self, "Dato requerido", "Debes ingresar la placa del vehículo."
                )
                return None
            if not es_placa_valida(identificador):
                QMessageBox.warning(self, "Placa inválida", MENSAJE_PLACA_INVALIDA)
                return None

        return ConsultaParams(
            modo=modo,
            identificador=identificador,
            tipo_documento=tipo_doc,
        )

    def _iniciar_consulta(self, params: ConsultaParams) -> None:
        self._ultimos_params = params
        self._set_controles_consulta_activos(False)

        if params.modo == "DOCUMENTO":
            self.lbl_estado.setText("Consultando en RUNT y SIMIT en paralelo…")
            self._set_progreso_fuente("RUNT", "en_curso")
            self._set_progreso_fuente("SIMIT", "en_curso")
            self.log(
                f"Iniciando consulta documento: "
                f"tipo={params.tipo_documento}, número={params.identificador}"
            )
        else:
            self.lbl_estado.setText("Consultando en SIMIT por placa…")
            self._set_progreso_fuente("RUNT", "omitido")
            self._set_progreso_fuente("SIMIT", "en_curso")
            self.log(f"Iniciando consulta placa: {params.identificador}")

        self._thread = QThread(self)
        self._worker = ConsultaWorker(params=params, debug=get_settings().debug)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.log.connect(self._on_worker_log)
        self._worker.progreso.connect(self._on_worker_progreso)
        self._worker.captchaRequested.connect(self._on_captcha_requested)

        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    @pyqtSlot(str)
    def _on_worker_log(self, msg: str):
        self.log(msg)

    @pyqtSlot(str, str)
    def _on_worker_progreso(self, fuente: str, estado: str):
        self._set_progreso_fuente(fuente, estado)

    @pyqtSlot(object)
    def _on_worker_finished(self, resultado):
        self._set_progreso_fuente("RUNT", resultado.estado_fuente_runt())
        self._set_progreso_fuente("SIMIT", resultado.estado_fuente_simit())
        self.lbl_estado.setText(resumen_estados_consulta(resultado))
        self.log("✅ Consulta finalizada.")
        formatear_resultado_consulta(resultado, self.log)

        if resultado.error_persistencia:
            QMessageBox.warning(
                self,
                "No se guardó en la base de datos",
                "La consulta se completó y los resultados se muestran aquí,\n"
                "pero no se pudieron guardar en Supabase/Postgres.\n\n"
                f"{resultado.error_persistencia}\n\n"
                "Puede usar «Reintentar consulta» para intentar de nuevo.",
            )

        recuperacion = mensajes_recuperacion(resultado)
        if recuperacion:
            QMessageBox.warning(
                self,
                "Consulta con fallos — puede reintentar",
                "\n\n".join(recuperacion),
            )

        self._set_controles_consulta_activos(True)

    @pyqtSlot(str)
    def _on_worker_error(self, error_msg: str):
        self.lbl_estado.setText("Error durante la consulta.")
        # Conservar último estado conocido; marcar como error genérico si seguía en curso
        for lbl, fuente in (
            (self.lbl_progreso_runt, "RUNT"),
            (self.lbl_progreso_simit, "SIMIT"),
        ):
            if "en curso" in lbl.text().lower():
                self._set_progreso_fuente(fuente, "error")
        self.log(f"Error: {error_msg}")
        QMessageBox.critical(
            self,
            "Error en la consulta",
            f"Ocurrió un error inesperado:\n{error_msg}\n\n"
            "Acción: use «Reintentar consulta» sin cerrar la aplicación.\n"
            "Si el fallo menciona RUNT o SIMIT, esa es la fuente afectada.",
        )
        self._set_controles_consulta_activos(True)

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
