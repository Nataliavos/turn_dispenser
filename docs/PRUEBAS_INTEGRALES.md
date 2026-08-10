# Pruebas integrales del flujo completo (E-02)

Checklist y acta para validar readiness previo al piloto (E-03).

Cubre: **entrada → automatización (mock/manual) → extracción → persistencia → UI**,
con config/logs y ausencia de lógica de elegibilidad.

**Relacionado:** [`VALIDACION_PERSISTENCIA.md`](VALIDACION_PERSISTENCIA.md) (D-04) ·
[`persistencia.md`](persistencia.md) · [`supabase-local.md`](supabase-local.md) ·
[`RUNBOOK_PILOTO.md`](RUNBOOK_PILOTO.md) (E-03).

---

## Criterios go / no-go (piloto E-03)

| Criterio | Go si… |
|----------|--------|
| Automatizado offline | Nivel A (smoke + unitarios + flujo mock) en verde |
| Persistencia | Nivel D (D-04) PASS con Supabase Docker, o defectos no bloqueantes documentados |
| Entrada | Validación documento/placa rechaza inválidos sin consultar portales |
| UX recuperación | Tras error/parcial hay camino de reintento (E-01) sin cerrar la app |
| CAPTCHA | RUNT sigue siendo manual (sin bypass) — checklist manual B/C |
| Elegibilidad | Ningún mensaje/columna `apto` / `puede_tramitar` / `elegible` en flujo validado |
| Blockers | Ningún blocker crítico de flujo abierto sin mitigación |

**Veredicto:** ver sección [Acta de ejecución](#acta-de-ejecución).

---

## Prerrequisitos

```bash
cd /ruta/a/turn_dispenser
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install chromium   # solo para pasada manual con portales
```

1. Docker + stack Supabase arriba (`docker ps` → `supabase_db_*`).
2. Migraciones aplicadas (`supabase db reset` o `./scripts/apply_local_migrations.sh`).
3. `DATABASE_URL` exportada o en `.env` (ver `.env.example`).
4. `PERSISTENCIA_ENABLED=true` (default).
5. Entorno gráfico para checklist GUI (CAPTCHA).

Los escenarios **automatizados** no abren Chromium: mockean RUNT/SIMIT.
La pasada **manual** (sección C) usa portales reales.

---

## Cómo repetir (automatizado)

```bash
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
python scripts/verificar_flujo_integral.py
```

Equivale a:

1. Smoke de imports (`ConsultaController`, GUI, settings).
2. `pytest` suites offline + `tests/test_flujo_integral.py`.
3. Si hay BD: `pytest tests/test_persistencia_e2e.py` (D-04).

Salida esperada: `RESULTADO GLOBAL: PASS` (o `PASS_PARCIAL` si omitió D-04).

---

## Niveles de la batería

### Nivel A — Automatizado sin portales

| # | Escenario | Comando / cobertura | Esperado |
|---|-----------|---------------------|----------|
| A1 | Smoke imports | incluido en `verificar_flujo_integral.py` | Sin error |
| A2 | Validación documento/placa | `test_documento_validator` + `test_flujo_integral` | Rechaza inválidos |
| A3 | Errores por fuente / progreso | `test_errores_fuentes` | Parcial no tumba la otra fuente |
| A4 | Parsers + helpers | `test_*_parser`, `test_parse_helpers` | Fixtures OK |
| A5 | Flujo DOCUMENTO/PLACA mock | `test_flujo_integral` | Estados, formateo, sin elegibilidad |
| A6 | Recuperación E-01 | `mensajes_recuperacion` en A5 | Sugiere «Reintentar consulta» |

### Nivel D — Persistencia (Supabase Docker) — enlace D-04

Detalle y criterios: [`VALIDACION_PERSISTENCIA.md`](VALIDACION_PERSISTENCIA.md).

| # | Escenario | Automatización |
|---|-----------|----------------|
| D1 | DOCUMENTO ok | `test_e2e_01_*` |
| D2 | DOCUMENTO parcial | `test_e2e_02_*` |
| D3 | PLACA ok (sin fila RUNT) | `test_e2e_03_*` |
| D4 | Fallo BD | `test_e2e_04_*` |
| D5 | JSONB / sin columnas elegibilidad | `test_e2e_json_*` + assert esquema |

### Nivel B — Config, logs y arranque GUI (semi-manual)

| # | Escenario | Pasos | Esperado |
|---|-----------|-------|----------|
| B1 | Config/env | Revisar `.env` / `get_settings()`: `DATABASE_URL`, `PERSISTENCIA_ENABLED`, `BROWSER_HEADLESS=false` | Headless false en operación (CAPTCHA) |
| B2 | Logs | Con `LOG_FILE=logs/turn_dispenser.log` o stderr: una consulta mock/manual deja `cid=` | Correlación presente |
| B3 | GUI arranque | `python app_gui.py` | Ventana; radios Documento/Placa; labels RUNT/SIMIT; botón Reintentar deshabilitado al inicio |

### Nivel C — Manual con portales (opcional si no hay datos/CAPTCHA)

Usar datos locales del equipo (no commitear identificadores).

| # | Escenario | Pasos | Esperado |
|---|-----------|-------|----------|
| C1 | GUI DOCUMENTO | Consultar + CAPTCHA manual | Progreso por fuente; resultados; persistencia o aviso |
| C2 | GUI PLACA | Placa válida | Solo SIMIT; RUNT «—» |
| C3 | Validación GUI | Placa/documento inválido | Warning; no arranca consulta |
| C4 | Parcial / error | Forzar fallo de una fuente o CAPTCHA mal | Diálogo recuperación + Reintentar (E-01) |
| C5 | Reintento | «Reintentar consulta» | Nueva corrida; CAPTCHA de nuevo si aplica |
| C6 | CLI RUNT | `python app.py --tipo CC --numero …` | CAPTCHA stdin; formateo; sin mensajes de trámite |

---

## Ausencia de lógica de elegibilidad

Confirmado en:

- Modelos / formatter (`test_flujo_integral`, `test_modelos_dominio`).
- Esquema Postgres (`information_schema` en D-04).
- UX: no aparecen `apto` / `puede tramitar` / `elegible`.

`tiene_multas_inferidas` es heurística RUNT etiquetada como **no elegibilidad**.

---

## Defectos (plantilla)

| ID | Severidad | Descripción | Estado | Mitigación |
|----|-----------|-------------|--------|------------|
| — | — | Ninguno en esta pasada / completar | — | — |

Severidades: **Blocker** (rompe flujo mostrador) · **Major** · **Minor** · **Nota**.

Solo se corrigen en E-02 los **blockers** de flujo; el resto se reporta.

---

## Acta de ejecución

| Campo | Valor |
|-------|--------|
| Fecha (UTC) | 2026-07-30 19:34:56Z |
| Rama | `test/E-02-pruebas-integrales-flujo-completo` |
| Entorno | Supabase local Docker (`supabase_db_nataliavos`, `:54322`) + `.venv` Python 3.12 |
| Comando | `DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres python scripts/verificar_flujo_integral.py` |
| Nivel A | **PASS** (A1 smoke + 55 tests offline/flujo mock) |
| Nivel D (D-04) | **PASS** (5/5 `test_persistencia_e2e`) |
| Nivel B (manual) | **PASS parcial** — B3 GUI smoke (widgets Reintentar/progreso) OK en `DISPLAY=:0`; B1/B2 no re-ejecutados con LOG_FILE en esta pasada (defaults `.env.example` revisados) |
| Nivel C (portales) | **Omitido** — sin corrida CAPTCHA/RUNT/SIMIT reales en esta sesión (requiere datos locales del equipo) |
| Blockers abiertos | Ninguno |
| Elegibilidad en flujo | **Confirmado ausente** (tests A5 + esquema D-04; disclaimer «no elegibilidad» en formatter permitido) |
| **Veredicto E-03** | **LISTO CON MITIGACIONES** |

### Mitigaciones / follow-up antes del piloto

1. Completar Nivel C (GUI DOCUMENTO + CAPTCHA + PLACA) con datos de prueba del CRC en la preparación E-03 / runbook.
2. Asegurar `DATABASE_URL` en `.env` de cada estación (en esta máquina el DSN se exportó en shell; el archivo `.env` local no lo tenía).
3. Usar este documento (`PRUEBAS_INTEGRALES.md`) como checklist operativo; no depender de guías de Fase 1 archivadas.

### Defectos encontrados en esta pasada

| ID | Severidad | Descripción | Estado | Mitigación |
|----|-----------|-------------|--------|------------|
| — | — | Ninguno | — | — |

### Notas de ejecución

- RESULTADO GLOBAL del script: **PASS**.
- Persistencia E2E y flujo mock cubren DOCUMENTO ok/parcial, PLACA, fallo BD y ausencia de columnas de elegibilidad.
- Reintento operativo (E-01) validado en tests de recuperación; CAPTCHA manual no se ejerció en vivo (mitigación #1).
