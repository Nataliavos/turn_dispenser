

🧭 Guía práctica para trabajar día a día usando **CMD**.

---

## 🚀 INICIO DE JORNADA (CMD)

1) Abrir el proyecto
```cmd
cd /d D:\TESLA\turn_dispenser

2) Abrir el proyecto
venv\Scripts\activate.bat

3) Instalar / sincronizar dependencias
pip install -r requirements.txt

4) Verificar Playwright (Chromium)
python -m playwright install chromium

5) Ejecutar
python app_gui.py


🧪 DURANTE EL DESARROLLO

- Probar primero en GUI (python app_gui.py)
- Mantener Playwright en services/runt_playwright.py (solo automatización)
- Mantener parseo en services/runt_parser.py
- Mantener lógica de orquestación en controllers/runt_controller.py

✅ FIN DE JORNADA (CMD)

1. Revisar cambios
git status

2. Guardar cambios
git add .
git commit -m "Describe lo que hiciste"
git push

3. Si cambiaste dependencias
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Actualiza dependencias"
git push

4. Cerrar entorno virtual
deactivate