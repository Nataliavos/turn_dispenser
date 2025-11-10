# 🌀 Turn Dispenser

Aplicación automatizada que interactúa con un navegador web para gestionar turnos en línea.  
Actualmente desarrollada en **Python** usando **Playwright**, y diseñada para evolucionar hacia una **versión de escritorio**.

---

## 🚀 Requisitos previos

Asegúrate de tener instalado en tu equipo:

- [Python 3.10 o superior](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)
- Un editor de código (por ejemplo, [VS Code](https://code.visualstudio.com/))

---

## ⚙️ Instalación

1. **Clona el repositorio:**
   ```bash
   git clone https://github.com/<tu_usuario>/<tu_repositorio>.git
   cd turn_dispenser

2. Crea y activa el entorno virtual:

En Windows (PowerShell):
python -m venv venv
venv\Scripts\activate

En Windows (CMD):
python -m venv venv
venv\Scripts\activate.bat

En Linux/Mac:
python3 -m venv venv
source venv/bin/activate

3. Instala las dependencias:
pip install -r requirements.txt

4. Instala los navegadores de Playwright:
playwright install


▶️ Ejecución del programa

Para ejecutar el test principal (abrir el navegador y realizar la automatización):
python test_browser.py

⚠️ Si el navegador se cierra muy rápido, puedes usar el modo “slow motion” modificando
slow_mo=1000 en el archivo test_browser.py (eso retrasa cada acción 1 segundo).

🧩 Estructura del proyecto

turn_dispenser/
│
├── test_browser.py          # Script principal de automatización
├── app_test_playwright.py   # Archivo auxiliar (en desarrollo)
├── requirements.txt         # Dependencias del proyecto
├── .gitignore               # Archivos que no se suben al repositorio
└── README.md                # Este archivo

💡 Próximos pasos

 Implementar la interfaz de escritorio (Tkinter o PyQt)

 Automatizar ingreso de tipo y número de documento en el RUNT

 Integrar lectura de datos desde Excel o base de datos

 Mejorar la gestión de errores y logs

 Añadir pruebas automatizadas

 👩‍💻 Autor

Natalia Vargas Osorio
📍 Medellín, Colombia
💻 Técnica en Desarrollo de Software
📚 Aprendizaje en curso: Python, JavaScript, React, Node.js

🔗 Perfil de GitHub

📝 Licencia

Este proyecto se distribuye bajo la licencia MIT, lo que significa que puedes usarlo, copiarlo y modificarlo libremente, siempre que mantengas el crédito correspondiente.

