# 🧭 WORKFLOW – Proyecto turn_dispenser

Guía práctica para iniciar y cerrar tu jornada de desarrollo en el proyecto **turn_dispenser**  
(Estructura basada en Python + Playwright + entorno virtual)

---

## 🚀 CHECKLIST DE INICIO DIARIO

### 1. Abre tu proyecto
En PowerShell o terminal:
```bash
cd Desktop/turn_dispenser


2. Activa el entorno virtual
venv\Scripts\activate
Verás (venv) al inicio de la línea.

3. Actualiza el entorno (si trabajas desde otro PC o hubo cambios)
pip install -r requirements.txt

4. Comprueba que Playwright está listo
python -m playwright install

5. Abre tu IDE o ejecuta el script principal
python test_browser.py
Usa este paso para probar el funcionamiento de tu automatización.



✅ CHECKLIST DE FIN DE JORNADA
1. Guarda tu trabajo

Asegúrate de que todos los archivos están guardados en tu IDE.

2. Verifica los cambios realizados
git status
Revisa qué archivos cambiaste o agregaste.

3. Actualiza el control de versiones
git add README.md requirements.txt app_test_playwright.py test_browser.py
git commit -m "Describe brevemente lo que hiciste hoy"
git push

💡 Si instalaste nuevos paquetes con pip:
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Actualiza dependencias"
git push

4. Verifica que todo esté limpio
git status

5. Cierra el entorno virtual
deactivate

📘 Consejo:
Si cambias de equipo, recuerda que solo necesitas:

Clonar el repositorio desde GitHub

Instalar dependencias con pip install -r requirements.txt

Ejecutar python -m playwright install una sola vez para descargar los navegadores.