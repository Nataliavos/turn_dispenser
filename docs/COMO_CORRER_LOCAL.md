# Cómo correr Turn Dispenser en local

Guía de **entrega / puesta en marcha** para quien reciba el proyecto y deba ejecutarlo en su máquina (Linux recomendado; Windows posible con matices).

**Audiencia:** responsable técnico o supervisor que no necesita conocer el código interno.  
**Qué responde la app:** *¿Qué reportan RUNT y SIMIT?*  
**Qué no hace:** no decide si un ciudadano puede tramitar (sin “apto” / “elegible”).

| Documento | Cuándo usarlo |
|-----------|----------------|
| **Este archivo** | Primera instalación y arranque diario |
| [`RUNBOOK_PILOTO.md`](RUNBOOK_PILOTO.md) | Operación en mostrador / CRC piloto |
| [`supabase-local.md`](supabase-local.md) | Detalle Docker + migraciones + Studio |
| [`../INSTRUCCIONES_UBUNTU.md`](../INSTRUCCIONES_UBUNTU.md) | Problemas típicos de Ubuntu / Qt / Playwright |
| [`../README.md`](../README.md) | Visión general del repo |

---

## 1. Requisitos

| Requisito | Notas |
|-----------|--------|
| **Python 3.10+** | `python3 --version` |
| **Git** | Para clonar o actualizar el repo |
| **Entorno gráfico** | Obligatorio para la GUI y el CAPTCHA de RUNT |
| **Internet** | Portales RUNT y SIMIT |
| **Docker** | Persistencia local (Postgres vía Supabase) |
| **Supabase CLI** | [Instalación](https://supabase.com/docs/guides/local-development/cli/getting-started) — `supabase --version` |
| **RAM** | ≥ 4 GB libres (modo documento abre 2 Chromium) |

Sin Docker la GUI **sí puede consultarse**, pero no guardará historial si `PERSISTENCIA_ENABLED=true` (verás aviso en pantalla). Para piloto completo, levanta el stack.

---

## 2. Obtener el código

```bash
# Ejemplo: clonar
git clone <url-del-repo> turn_dispenser
cd turn_dispenser

# O si ya tienes la carpeta:
cd /ruta/a/turn_dispenser
git checkout main
git pull
```

---

## 3. Entorno Python (una vez por máquina)

Usa **`.venv`** (nombre recomendado en este proyecto):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# En Windows CMD:  .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Si Chromium falla en Ubuntu:

```bash
python -m playwright install-deps chromium
python -m playwright install chromium
```

Cada vez que abras una terminal nueva:

```bash
cd /ruta/a/turn_dispenser
source .venv/bin/activate
```

---

## 4. Configuración (`.env`)

```bash
cp .env.example .env
```

Edita `.env` y deja al menos:

```bash
APP_ENV=local
DEBUG=true
BROWSER_HEADLESS=false
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
PERSISTENCIA_ENABLED=true
```

- **`BROWSER_HEADLESS=false`** es obligatorio: el CAPTCHA de RUNT se resuelve a mano.
- **`DATABASE_URL`** apunta al Postgres del Supabase local (puerto **54322**).
- Opcional: `OPERADOR`, `ESTACION`, `LOG_FILE=logs/turn_dispenser.log`.

No subas `.env` a git (ya está en `.gitignore`).

---

## 5. Base de datos local (Supabase + Docker)

### 5.1 Arranque del stack

```bash
# Docker debe estar en marcha
docker info

# Desde la raíz del repo (si el disco se puede montar en Docker: ext4, etc.)
supabase start
supabase status          # anotar URL de Studio y keys
```

Studio (interfaz web de tablas): suele ser **http://127.0.0.1:54323**  
(la URL exacta la imprime `supabase status`).

### 5.2 Aplicar migraciones (esquema)

**Caso A — repo en disco “normal” (home, ext4):**

```bash
supabase db reset
```

**Caso B — repo en NTFS / `/media/...` (Docker no monta bien):**

```bash
# Arranca Supabase desde un directorio en home si hace falta, luego:
./scripts/apply_local_migrations.sh

# Si hay varios contenedores, fuerza el nombre:
DB_CONTAINER=supabase_db_<nombre> ./scripts/apply_local_migrations.sh
```

Comprobar tablas:

```bash
docker exec -i "$(docker ps --format '{{.Names}}' | grep '^supabase_db_' | head -1)" \
  psql -U postgres -d postgres -c '\dt public.*'
```

Debes ver, entre otras: `consultas`, `resultados_runt`, `resultados_simit`, `eventos_consulta`,  
`personas`, `vehiculos`, hechos tipados (`licencias`, `obligaciones_simit`, …).

Smoke rápido de conexión:

```bash
source .venv/bin/activate
python scripts/smoke_persistencia.py
```

Detalle: [`supabase-local.md`](supabase-local.md).

---

## 6. Ejecutar la aplicación

Con `.venv` activo y Docker/Supabase arriba (si usas persistencia):

```bash
# GUI (recomendado)
python app_gui.py

# Consola — solo RUNT por documento
python app.py --tipo CC --numero <documento>
```

### Uso básico en GUI

1. **Documento:** tipo + número → **Consultar** → resolver CAPTCHA RUNT → ver RUNT + SIMIT.
2. **Placa:** solo SIMIT (sin CAPTCHA RUNT).
3. **Reintentar consulta:** repite la última corrida (nuevo CAPTCHA si aplica).
4. **Nueva consulta:** limpia la pantalla para el siguiente ciudadano; **no borra** el historial en BD.

---

## 7. Arranque diario (resumen)

```bash
# 1. Docker Desktop / daemon en marcha
# 2. Terminal:
cd /ruta/a/turn_dispenser
source .venv/bin/activate
supabase start          # si el stack no está arriba
python app_gui.py
```

Al cerrar el turno (opcional):

```bash
supabase stop
deactivate
```

---

## 8. Qué esperar en la base de datos

Tras consultas reales con `PERSISTENCIA_ENABLED=true`:

| Tabla / capa | Contenido |
|--------------|-----------|
| `consultas` | 1 fila **por cada** Consultar/Reintentar (historial) |
| `resultados_runt` / `resultados_simit` | Snapshot 1:1 de la corrida (`raw_html` incluido si hubo OK) |
| `personas` / `vehiculos` | Maestros (upsert: misma CC/placa → 1 fila) |
| Hechos tipados | Licencias, obligaciones SIMIT, etc., según lo reportado |

**Nueva consulta** en la GUI no elimina filas.

---

## 9. Verificaciones opcionales

```bash
# Parsers offline (sin red)
pip install -r requirements-dev.txt
pytest tests/test_runt_parser.py tests/test_simit_parser.py -v

# Persistencia / maestros (requiere BD)
python scripts/verificar_persistencia_e2e.py
python scripts/verificar_maestros_upsert_e2e.py

# Flujo integral (mocks)
python scripts/verificar_flujo_integral.py
```

---

## 10. Problemas frecuentes

| Síntoma | Qué hacer |
|---------|-----------|
| No abre la GUI | Sesión gráfica; `pip install PyQt6`; en Ubuntu: `libxcb-cursor0` |
| CAPTCHA no aparece / app “congelada” | `BROWSER_HEADLESS=false`; esperar; no cerrar |
| «No se guardó en la base de datos» | `docker ps`, `DATABASE_URL`, `supabase start`, migraciones |
| `supabase start` falla en `/media/...` | Usar `./scripts/apply_local_migrations.sh` (ver §5.2 B) |
| Playwright / Chromium | `python -m playwright install-deps chromium` |
| Reintentar deshabilitado | Normal al inicio o tras **Nueva consulta** |

Más detalle operativo: [`RUNBOOK_PILOTO.md`](RUNBOOK_PILOTO.md) §7.

---

## 11. Alcance actual del producto (entrega)

**Incluido:** consultas RUNT/SIMIT, GUI con reintento y nueva consulta, persistencia local (corridas + maestros/hechos), retención de `raw_html`, scripts de verificación.

**Fuera de alcance (a propósito):** motor de reglas de elegibilidad / “puede tramitar”; Supabase Cloud multi-sede; historial navegable en UI.

PRD: [`product-requirements-document.md`](product-requirements-document.md).
