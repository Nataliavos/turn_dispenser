# Guía: ejecutar turn_dispenser en Ubuntu Linux

Proyecto: **Turn Dispenser** (consulta RUNT + SIMIT con Playwright + PyQt6 + Supabase local).

> **Entrega / máquina nueva:** la guía canónica paso a paso es  
> [`docs/COMO_CORRER_LOCAL.md`](docs/COMO_CORRER_LOCAL.md).  
> Este archivo profundiza en Ubuntu (Qt, Playwright, rutas).

---

## Requisitos previos

- **Ubuntu** (o derivado: Linux Mint, etc.)
- **Python 3.10 o superior**
- **Conexión a internet** (portales RUNT/SIMIT)
- **Entorno gráfico** (X11/Wayland) y librerías Qt para la GUI
- **Docker** + **Supabase CLI** si quieres guardar historial en Postgres local

---

## 1. Comprobar Python

```bash
python3 --version
```

Si no tienes Python 3.10+:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

---

## 2. Ir a la carpeta del proyecto

```bash
cd /ruta/donde/esté/turn_dispenser
```

---

## 3. Crear entorno virtual (solo la primera vez)

Se recomienda el nombre **`.venv`** (alineado al resto de la documentación):

```bash
python3 -m venv .venv
```

---

## 4. Activar el entorno virtual

```bash
source .venv/bin/activate
```

Deberías ver el prefijo `(.venv)` en la terminal.

---

## 5. Dependencias Python + Chromium

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Si la **GUI** falla por PyQt6:

```bash
pip install PyQt6
sudo apt install libxcb-cursor0 libxkbcommon-x11-0
```

Si Playwright/Chromium falla:

```bash
python -m playwright install-deps chromium
python -m playwright install chromium
```

---

## 6. Configuración `.env`

```bash
cp .env.example .env
```

Mínimo recomendado:

- `BROWSER_HEADLESS=false` (CAPTCHA RUNT manual)
- `DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`
- `PERSISTENCIA_ENABLED=true`

No versionar `.env`.

---

## 7. Base de datos (Supabase + Docker)

```bash
docker info                 # Docker en marcha
supabase start
supabase status             # Studio ≈ http://127.0.0.1:54323
```

Aplicar esquema:

```bash
# Disco local típico:
supabase db reset

# Repo en NTFS / /media/... (workaround):
./scripts/apply_local_migrations.sh
```

Detalle: [`docs/supabase-local.md`](docs/supabase-local.md).  
Smoke: `python scripts/smoke_persistencia.py`.

---

## 8. Ejecutar el programa

### GUI (recomendado)

```bash
source .venv/bin/activate
python app_gui.py
```

### Consola (solo RUNT)

```bash
python app.py --tipo CC --numero 1017259440
```

Sustituye tipo y número por los datos de prueba.

---

## 9. CAPTCHA

- **Consola:** se guarda `captcha.png` y la terminal pide el texto.
- **GUI:** diálogo con la imagen y un campo de texto.

Este proyecto **no** evade el CAPTCHA.

---

## 10. Arranque diario (resumen)

```bash
cd /ruta/a/turn_dispenser
source .venv/bin/activate
supabase start          # si no está arriba
python app_gui.py
```

Al terminar (opcional): `supabase stop` · `deactivate`.

---

## Resumen rápido (copiar y pegar)

```bash
cd /ruta/a/turn_dispenser
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# editar .env (BROWSER_HEADLESS=false, DATABASE_URL, PERSISTENCIA_ENABLED)
supabase start
./scripts/apply_local_migrations.sh   # o: supabase db reset
python scripts/smoke_persistencia.py
python app_gui.py
```

---

## Problemas frecuentes en Ubuntu

| Problema | Solución |
|----------|----------|
| `python: command not found` | Usa `python3`. |
| Error al importar PyQt6 | `pip install PyQt6` y `sudo apt install libxcb-cursor0 libxkbcommon-x11-0`. |
| Playwright no abre Chromium | `python -m playwright install-deps chromium` y luego `install chromium`. |
| No se muestra la ventana GUI | Sesión gráfica (no solo SSH sin X11). En SSH: `ssh -X` / `ssh -Y`. |
| No guarda en BD | Docker + `supabase start` + migraciones + `DATABASE_URL` en `.env`. |
| `supabase` falla en `/media/...` | Usa `./scripts/apply_local_migrations.sh` (ver `docs/supabase-local.md`). |

Operación de mostrador: [`docs/RUNBOOK_PILOTO.md`](docs/RUNBOOK_PILOTO.md).
