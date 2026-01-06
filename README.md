# 🌀 Turn Dispenser – Consulta Ciudadana RUNT

Aplicación en **Python** (Playwright) con:
- 🖥️ **Interfaz gráfica (PyQt6)** para consultar en el Portal Público del **RUNT**.
- 💻 **Modo consola (CMD)** para pruebas rápidas.

El usuario ingresa tipo y número de documento y resuelve el **CAPTCHA manualmente** (requisito del portal).

---

## ✅ Características

- Automatización con **Playwright**
- CAPTCHA manual (CLI o GUI)
- GUI multihilo (QThread) para no congelar la app
- Arquitectura por capas: `controllers / services / models / views`
- Base para parseo (`runt_parser.py`) y futuro guardado en DB

---

## 📁 Estructura del proyecto

turn_dispenser/
│
├── app.py # Entrada modo consola (CMD)
├── app_gui.py # Entrada modo GUI (PyQt6)
│
├── controllers/
│ └── runt_controller.py
│
├── models/
│ └── runt_models.py
│
├── services/
│ ├── runt_playwright.py
│ └── runt_parser.py
│
├── views/
│ ├── console_view.py
│ └── gui_qt.py
│
├── requirements.txt
├── README.md
├── INSTRUCCIONES_CMD.txt
└── WORKFLOW.md


> Nota: archivos legacy (si existen) se recomienda moverlos a `legacy/` para no confundir.

---

## ⚙️ Requisitos

- Windows
- Python 3.10+ instalado y agregado al PATH
- Conexión a internet

---

## 🔧 Instalación (CMD)

1) Abre **CMD** en la carpeta del proyecto (ejemplo):
```txt
D:\TESLA\turn_dispenser>

```cmd

2) Crea el entorno virtual:
python -m venv venv

3) Actívalo:
venv\Scripts\activate.bat

4) Instala dependencias:
python -m pip install --upgrade pip
pip install -r requirements.txt

5) Instala Chromium de Playwright:
python -m playwright install chromium


▶️ Ejecución (CMD)

GUI entorno gráfico (recomendado):
python app_gui.py

Consola:
python app.py --tipo CC --numero 1017259440


⚠️ Nota importante
Este proyecto no evade mecanismos de seguridad.
El CAPTCHA se resuelve manualmente por el usuario.

🧭 Estado
✅ Automatización + CAPTCHA OK
✅ GUI funcional
⏳ Parseo completo de resultados (en progreso)
⏳ Persistencia en base de datos (pendiente)
⏳ Barrido controlado (pendiente)