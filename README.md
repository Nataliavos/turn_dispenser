# Turn Dispenser

Aplicación de escritorio en **Python** que automatiza consultas a plataformas oficiales de tránsito en Colombia (**RUNT** y **SIMIT**) para reducir el tiempo operativo de funcionarios en CRC / centros de trámites.

**Pregunta que responde hoy:** *¿Qué reportan RUNT y SIMIT?*  
**No decide** si un ciudadano puede realizar un trámite (reglas de elegibilidad fuera de alcance).

### Empezar aquí (entrega / máquina nueva)

1. **Correr en local:** [`docs/COMO_CORRER_LOCAL.md`](docs/COMO_CORRER_LOCAL.md) ← guía paso a paso  
2. **Operación piloto (mostrador):** [`docs/RUNBOOK_PILOTO.md`](docs/RUNBOOK_PILOTO.md)  
3. **Producto (PRD):** [`docs/product-requirements-document.md`](docs/product-requirements-document.md)

---

## Entry points

| Comando | Uso |
|---------|-----|
| `python app_gui.py` | GUI PyQt6 (recomendado en mostrador) |
| `python app.py --tipo CC --numero <documento>` | Consola (consulta RUNT por documento) |

Los únicos entry points soportados son `app.py` y `app_gui.py`.  
La automatización vive en `services/` y se orquesta desde `controllers/`.

---

## Modos de consulta

| Modo | GUI | Consola (actual) |
|------|-----|------------------|
| **DOCUMENTO** (tipo + número) | RUNT + SIMIT en paralelo vía `ConsultaController` (CAPTCHA RUNT manual) | Solo RUNT vía `RuntController` |
| **PLACA** | Solo SIMIT (validación de formato de placa) | No disponible aún en CLI |

En modo placa, el portal público RUNT no aplica; solo SIMIT.

En la GUI: **Reintentar consulta** (misma entrada) y **Nueva consulta** (limpia pantalla; no borra BD).

---

## Stack

- Python 3.10+
- Playwright (Chromium) — automatización web
- BeautifulSoup4 — parseo HTML
- PyQt6 — interfaz gráfica
- python-dotenv — configuración externa (`.env`)
- Persistencia: **Supabase local con Docker** + `repositories/` (psycopg) — corridas, maestros y hechos tipados

Dependencias de runtime: [`requirements.txt`](requirements.txt).

---

## Instalación rápida

La guía completa (Docker, `.env`, migraciones, arranque diario) está en  
**[`docs/COMO_CORRER_LOCAL.md`](docs/COMO_CORRER_LOCAL.md)**.

### Linux / Ubuntu (código + GUI)

Detalle ampliado: [`INSTRUCCIONES_UBUNTU.md`](INSTRUCCIONES_UBUNTU.md).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# Editar .env: BROWSER_HEADLESS=false, DATABASE_URL, PERSISTENCIA_ENABLED
```

### Windows (CMD)

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env
```

### Base de datos (obligatoria para guardar historial)

```bash
# Docker en marcha + Supabase CLI instalado
supabase start
supabase status                    # Studio ≈ http://127.0.0.1:54323

# Migraciones (disco local típico):
supabase db reset

# Si el repo está en NTFS /media/...:
./scripts/apply_local_migrations.sh
```

Más detalle: [`docs/supabase-local.md`](docs/supabase-local.md).

---

## Ejecución

```bash
source .venv/bin/activate   # si no está activo
python app_gui.py

# Consola — RUNT por documento
python app.py --tipo CC --numero 1017259440
```

**CAPTCHA:** este proyecto no evade mecanismos de seguridad. El CAPTCHA de RUNT se resuelve **manualmente**.

Antes de lanzar automatización, la app valida formato básico:
- **Documento:** tipo soportado (`CC`, `CE`, `TI`, `RC`, `PPT`, `CD`, `PA`) + número (`utils/documento_validator.py`).
- **Placa:** formatos colombianos (`utils/placa_validator.py`).

---

## Configuración

```bash
cp .env.example .env
# editar .env según la estación
```

- Módulo: `config/settings.py` (`get_settings()`)
- Logging: `utils/logging_setup.py` (correlation id por consulta)
- Plantilla: [`.env.example`](.env.example) (sin secretos)
- Por defecto `BROWSER_HEADLESS=false` (CAPTCHA manual)
- Persistencia: `DATABASE_URL`, `PERSISTENCIA_ENABLED` — [`docs/persistencia.md`](docs/persistencia.md)

Scripts útiles:

| Script | Qué hace |
|--------|----------|
| `python scripts/smoke_persistencia.py` | Smoke conexión + insert |
| `python scripts/verificar_persistencia_e2e.py` | E2E capa operativa |
| `python scripts/verificar_maestros_upsert_e2e.py` | E2E maestros / hechos v2 |
| `python scripts/verificar_flujo_integral.py` | Flujo integral (mocks) |
| `python scripts/backfill_maestros.py` | Backfill desde snapshots |
| `python scripts/purge_raw_html.py` | Retención / nullify `raw_html` |

---

## Tests de parsers (offline)

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_runt_parser.py tests/test_simit_parser.py -v
```

Fixtures: [`fixtures/README.md`](fixtures/README.md).

---

## Estado del proyecto (entrega actual)

### Implementado

- Automatización Playwright de RUNT (CAPTCHA manual) y SIMIT
- Parseo estructurado con `raw_html` y fixtures/tests offline
- GUI: modos DOCUMENTO / PLACA, progreso por fuente, reintento, **Nueva consulta**
- Configuración `.env`, logging con correlation id, validación de entradas
- Persistencia post-consulta (capa A: `consultas` + `resultados_*` + eventos)
- Esquema v2: maestros (`personas`, `vehiculos`) y hechos tipados; normalización post-consulta
- Backfill desde snapshots y retención de `raw_html`
- Runbook de estación piloto y scripts de verificación

### Fuera de alcance (a propósito)

- Motor de reglas de elegibilidad / “puede tramitar”
- Supabase Cloud / multi-sede con RLS por estación
- Historial de consultas navegable en la UI
- CLI con modo placa / SIMIT (solo RUNT por documento)

---

## Estructura (resumen)

```text
turn_dispenser/
├── app.py / app_gui.py
├── config/          # settings desde entorno + defaults
├── controllers/     # orquestación (ConsultaController, Runt, Simit)
├── services/        # Playwright + parsers
├── models/          # dataclasses de resultados
├── views/           # GUI y consola
├── utils/
├── repositories/    # Postgres (psycopg) + normalización / purge / backfill
├── supabase/        # config CLI, migrations/, seed.sql
├── scripts/         # migraciones locales, smokes, verificaciones
├── docs/
│   ├── COMO_CORRER_LOCAL.md           # ← arranque en máquina nueva
│   ├── RUNBOOK_PILOTO.md
│   ├── product-requirements-document.md
│   ├── db-schema.md / DB_DESIGN_V2.md
│   ├── supabase-local.md
│   └── persistencia.md
├── .env.example
├── requirements.txt
└── INSTRUCCIONES_UBUNTU.md
```

---

## Contribución (Git / GitHub)

1. Actualizar `main`
2. Rama por ticket (`feat/...`, `fix/...`, `docs/...`, …)
3. Un ticket ≈ una rama ≈ un PR
4. Conventional Commits

Guía día a día: [`WORKFLOW.md`](WORKFLOW.md).
