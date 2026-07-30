# Turn Dispenser

Aplicación de escritorio en **Python** que automatiza consultas a plataformas oficiales de tránsito en Colombia (**RUNT** y **SIMIT**) para reducir el tiempo operativo de funcionarios en CRC / centros de trámites.

**Pregunta que responde hoy:** *¿Qué reportan RUNT y SIMIT?*  
**No decide** si un ciudadano puede realizar un trámite (reglas de elegibilidad fuera de alcance).

**Fuente de verdad del producto:** [`docs/product-requirements-document.md`](docs/product-requirements-document.md)

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

---

## Stack

- Python 3.10+
- Playwright (Chromium) — automatización web
- BeautifulSoup4 — parseo HTML
- PyQt6 — interfaz gráfica
- python-dotenv — configuración externa (`.env`)
- Persistencia: **Supabase local con Docker** + capa `repositories/` (psycopg). Integración en orquestación: D-03.

Dependencias de runtime: ver [`requirements.txt`](requirements.txt) (solo paquetes directos).

---

## Instalación rápida

### Linux / Ubuntu

Sigue la guía detallada: [`INSTRUCCIONES_UBUNTU.md`](INSTRUCCIONES_UBUNTU.md).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

### Windows (CMD)

```cmd
python -m venv venv
venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

---

## Ejecución

```bash
# GUI
python app_gui.py

# Consola — RUNT por documento
python app.py --tipo CC --numero 1017259440
```

**CAPTCHA:** este proyecto no evade mecanismos de seguridad. El CAPTCHA de RUNT se resuelve **manualmente**.

Antes de lanzar automatización, la app valida formato básico:
- **Documento:** tipo soportado (`CC`, `CE`, `TI`, `RC`, `PPT`, `CD`, `PA`) + número con longitud/caracteres razonables (`utils/documento_validator.py`).
- **Placa:** formatos colombianos conocidos (`utils/placa_validator.py`).

Pruebas integrales (E-02): [`docs/PRUEBAS_INTEGRALES.md`](docs/PRUEBAS_INTEGRALES.md) · `python scripts/verificar_flujo_integral.py`.  
Histórico Fase 1: [`PRUEBAS_FASE1.md`](PRUEBAS_FASE1.md).

---

## Tests de parsers (offline)

Suite sin red ni navegador sobre fixtures HTML anonimizados:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_runt_parser.py tests/test_simit_parser.py -v
```

Fixtures y guía para capturar/actualizar HTML: [`fixtures/README.md`](fixtures/README.md).

---

## Configuración

Parámetros de runtime (URLs, timeouts, `slow_mo`, headless, debug, logging) se cargan desde entorno con defaults seguros:

```bash
cp .env.example .env
# editar .env según la estación
```

- Módulo: `config/settings.py` (`get_settings()`)
- Logging: `utils/logging_setup.py` (`setup_logging()`, correlation id por consulta)
- Plantilla versionada: [`.env.example`](.env.example) (sin secretos)
- `.env` / `.env.local` están ignorados por git
- Por defecto `BROWSER_HEADLESS=false` (CAPTCHA RUNT manual)
- `LOG_LEVEL` / `LOG_FILE` opcionales (sin archivo por defecto; solo stderr)
- Variables `SUPABASE_*` / `DATABASE_URL` / `DB_CONNECT_TIMEOUT_S` / `PERSISTENCIA_ENABLED`
- Guía: [`docs/persistencia.md`](docs/persistencia.md)
- Smoke: `python scripts/smoke_persistencia.py`
- E2E persistencia: `python scripts/verificar_persistencia_e2e.py` · [`docs/VALIDACION_PERSISTENCIA.md`](docs/VALIDACION_PERSISTENCIA.md)
- Flujo integral: `python scripts/verificar_flujo_integral.py` · [`docs/PRUEBAS_INTEGRALES.md`](docs/PRUEBAS_INTEGRALES.md)

---

## Base de datos local (Supabase + Docker)

```bash
# Requisitos: Docker + Supabase CLI
supabase start
supabase db reset   # aplica supabase/migrations + seed

# Workaround si el repo está en NTFS /media/... (Docker no monta):
./scripts/apply_local_migrations.sh
# Reaplicar esquema desde cero (solo local):
./scripts/apply_local_migrations.sh --reset
```

- Arranque / parada / variables: [`docs/supabase-local.md`](docs/supabase-local.md)
- Entidades, índices, retención `raw_html`: [`docs/db-schema.md`](docs/db-schema.md)

---

## Estado del proyecto

### Implementado

- Automatización Playwright de RUNT (CAPTCHA manual) y SIMIT
- Parseo estructurado (`runt_parser`, `simit_parser`) con `raw_html`
- GUI con modos DOCUMENTO / PLACA y orquestación `ConsultaController`
- Arquitectura por capas: `views` → `controllers` → `services` → `models` / `utils`
- Dependencias de runtime acotadas (A-02)
- Configuración externa vía `.env` / defaults (`config/`) (B-01)
- Logging estructurado con niveles y correlation id (B-02)
- Validación de entradas de documento (tipo + número) en GUI/CLI (B-03)
- Manejo unificado de errores por fuente RUNT/SIMIT (B-04)
- Modelos de dominio tipados / versionados (C-01)
- Fixtures HTML + tests offline de parsers (C-02)
- Helpers compartidos parsers/Playwright (C-03)
- Esquema BD + Supabase local Docker (D-01)
- Capa de conexión y repositorios Postgres/Supabase (D-02)
- Persistencia automática post-consulta en GUI/CLI (D-03)
- Verificación E2E de persistencia documentada (D-04)

### Pendiente (alineado al PRD)

- Piloto operativo / runbook (Fase E)
- Motor de reglas de elegibilidad (**fuera de alcance** hasta que el negocio lo defina)

---

## Estructura (resumen)

```text
turn_dispenser/
├── app.py / app_gui.py
├── config/          # settings desde entorno + defaults
├── controllers/     # orquestación (ConsultaController, Runt, Simit)
├── services/        # Playwright + parsers + helpers compartidos
├── models/          # dataclasses de resultados
├── views/           # GUI y consola
├── utils/           # validación de placa, etc.
├── docs/
│   ├── product-requirements-document.md   # PRD oficial
│   ├── db-schema.md                       # esquema de persistencia
│   ├── supabase-local.md                  # arranque Supabase + Docker
│   ├── persistencia.md                    # repositorios / DATABASE_URL
│   └── VALIDACION_PERSISTENCIA.md         # checklist E2E (D-04)
│   └── PRUEBAS_INTEGRALES.md              # acta flujo completo (E-02)
├── repositories/    # conexión psycopg + ConsultaRepository (D-02)
├── supabase/        # config CLI, migrations/, seed.sql
├── scripts/         # migraciones locales, smoke y verificación E2E
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── INSTRUCCIONES_UBUNTU.md
├── WORKFLOW.md
└── PLAN_DESARROLLO.md   # archivado; ver nota interna
```

---

## Contribución (Git / GitHub)

Flujo recomendado:

1. Actualizar `main`
2. Crear una rama por ticket con Conventional Commits, p. ej.:
   - `feat/...`, `fix/...`, `chore/...`, `docs/...`, `refactor/...`, `test/...`
3. Un ticket ≈ una rama ≈ un PR hacia `main`
4. Título de commit/PR al estilo: `docs(A-03): alinear documentación al PRD y al código`

No versionar documentos de trabajo personal (tickets internos, auditoría, backlog local). El PRD en `docs/` sí es documentación oficial del producto.

Guía día a día: [`WORKFLOW.md`](WORKFLOW.md).
