# Workflow diario — Turn Dispenser

Guía práctica para desarrollar y probar sin contradecir el [PRD](docs/product-requirements-document.md).

---

## Inicio de jornada

```bash
cd /ruta/al/turn_dispenser
git checkout main
git pull origin main

# Activar venv (Linux)
source .venv/bin/activate
# Windows CMD: venv\Scripts\activate.bat

pip install -r requirements.txt
python -m playwright install chromium   # si hace falta
```

Ubuntu: ver también [`INSTRUCCIONES_UBUNTU.md`](INSTRUCCIONES_UBUNTU.md).

---

## Durante el desarrollo

1. Crear rama desde `main` (Conventional Commits), por ejemplo:
   - `docs/A-03-...`, `feat/B-01-...`, `chore/...`
2. Implementar **solo** el alcance del ticket.
3. Probar:
   - GUI: `python app_gui.py` (DOCUMENTO = RUNT+SIMIT; PLACA = SIMIT)
   - Consola: `python app.py --tipo CC --numero <doc>` (hoy: solo RUNT)
4. Respetar capas:
   - `views/` — UI / CLI
   - `controllers/` — orquestación
   - `services/` — Playwright y parsers
   - `models/` — dataclasses
   - `utils/` — helpers (p. ej. placa)

**No** introducir reglas de elegibilidad (“puede / no puede tramitar”).

---

## Dependencias

- Runtime: editar solo [`requirements.txt`](requirements.txt) (paquetes **directos**).
- Dev (futuro): [`requirements-dev.txt`](requirements-dev.txt).
- **No** uses `pip freeze > requirements.txt` (vuelve a hinchar transitivas). Si agregas un paquete usado en código, añádelo a mano en `requirements.txt`.

---

## Fin de jornada / PR

```bash
git status
git add <archivos del ticket>
git commit -m "tipo(alcance): resumen en inglés o español claro"
git push -u origin HEAD
gh pr create   # o abrir PR desde GitHub
```

Un ticket ≈ una rama ≈ un PR hacia `main`.

---

## Referencias

- Producto: [`docs/product-requirements-document.md`](docs/product-requirements-document.md)
- Arranque local: [`docs/COMO_CORRER_LOCAL.md`](docs/COMO_CORRER_LOCAL.md)
- Pruebas integrales: [`docs/PRUEBAS_INTEGRALES.md`](docs/PRUEBAS_INTEGRALES.md)
