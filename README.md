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
- Persistencia prevista: **Supabase local con Docker** (PostgreSQL del stack Supabase). Aún no implementada.

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

Validación manual histórica (no sustituye tests automatizados): [`PRUEBAS_FASE1.md`](PRUEBAS_FASE1.md).

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
- Variables `SUPABASE_*` / `DATABASE_URL` están documentadas como placeholders para Fase D; aún no se usan en runtime

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

### Pendiente (alineado al PRD)

- Validación robusta de documento (B-03)
- Unificación de errores por fuente (B-04)
- Normalización de modelos + fixtures/tests de parsers (Fase C)
- Persistencia con **Supabase + Docker** (Fase D)
- Piloto operativo / runbook (Fase E)
- Motor de reglas de elegibilidad (**fuera de alcance** hasta que el negocio lo defina)

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
├── utils/           # validación de placa, etc.
├── docs/
│   └── product-requirements-document.md   # PRD oficial
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
