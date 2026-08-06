# Persistencia (D-02/D-03) — conexión, repositorios e integración post-consulta

Capa Python para leer/escribir hechos oficiales en el **Postgres de Supabase local**,  
y guardado automático al finalizar cada consulta en GUI/CLI.

## Decisión de cliente

| Opción | ¿Elegida? | Motivo |
|--------|-----------|--------|
| **`psycopg` v3** (SQL directo) | **Sí** | Simple, tipado, sin ORM; suficiente para el esquema D-01. |
| SQLAlchemy / supabase-py | No (por ahora) | Overhead innecesario para escritorio + DSN local. |

La app se conecta con el rol de `DATABASE_URL` (típicamente `postgres` en local), que **bypasa RLS**. No usar la anon key para escritura desde el instalador del operador.

## Configuración

Plantilla: [`.env.example`](../.env.example).

```bash
cp .env.example .env
# DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
# DB_CONNECT_TIMEOUT_S=10
# PERSISTENCIA_ENABLED=true   # false = no escribe BD (útil en desarrollo)
# OPERADOR= / ESTACION= / APP_VERSION=   # opcionales en cabecera
```

Cómo levantar el stack y obtener el DSN: [`supabase-local.md`](supabase-local.md).  
Esquema: [`db-schema.md`](db-schema.md).

## Flujo post-consulta (D-03 / F-02)

1. `ConsultaController.consultar` (GUI) o CLI RUNT finaliza hechos en `ResultadoConsulta`.
2. `intentar_persistir_resultado` (`controllers/persistencia_post_consulta.py`):
   1. **Snapshot capa A** (obligatorio si `PERSISTENCIA_ENABLED`): inserta `consultas` + upsert `resultados_runt` / `resultados_simit` + evento `PERSISTIDO`.
   2. **Normalización capas B/C** (best-effort): upsert maestros (`personas`, `vehiculos`, `persona_vehiculo`) y hechos tipados (`licencias`, `infracciones_runt`, `obligaciones_simit`, `acuerdos_pago_simit`); actualiza `consultas.persona_id` / `vehiculo_id`.
3. Política ante fallo:
   - Fallo de **snapshot**: resultados en pantalla; `persistido=False` + `error_persistencia`.
   - Fallo de **normalización**: el snapshot **permanece**; log/evento con `cid` (`NORMALIZACION_FALLIDA`); no se oculta el resultado en UI.
4. Persistencia **síncrona** (sin cola). CAPTCHA y paralelismo RUNT∥SIMIT sin cambios.

Misma CC/placa N veces → N filas en `consultas`, 1 maestro (`personas` / `vehiculos`).  
SIMIT `sin_pendientes`: snapshot OK y **cero** obligaciones nuevas.

Campos en `ResultadoConsulta`: `persistido`, `consulta_db_id`, `error_persistencia`, `persistencia_omitida`.

## API (módulo `repositories/`)

- `Database` / `get_database()` — conexión y `ping()`.
- `ConsultaRepository`:
  - `persistir_resultado_consulta(ResultadoConsulta)` — snapshot capa A.
  - `normalizar_maestros_y_hechos(consulta_id, ResultadoConsulta)` — upsert B/C.
  - `crear_consulta` / `actualizar_estado_consulta`
  - `guardar_resultado_runt` / `guardar_resultado_simit`
  - `agregar_evento` / `listar_eventos`
  - `obtener_por_id`
- Mappers: `repositories/mappers.py` (snapshot) y `repositories/normalizacion_mappers.py` (plan B/C).
- Errores: `ConexionPersistenciaError`, `PersistenciaError` (logging vía B-02; sin `print` como canal principal).

## Probar

```bash
# Dependencias
pip install -r requirements.txt -r requirements-dev.txt

# Smoke insert+select (requiere Docker/Supabase + migraciones)
python scripts/smoke_persistencia.py

# Unitarios (sin BD) + integración (skip si no hay Postgres)
pytest tests/test_persistencia_mappers.py \
       tests/test_normalizacion_mappers.py \
       tests/test_persistencia_integracion.py \
       tests/test_persistencia_post_consulta.py -v
```

Si el smoke falla por conexión: confirma `docker ps` (`supabase_db_*`), puerto **54322**, y `./scripts/apply_local_migrations.sh` si hace falta.

## Verificación E2E (D-04)

Checklist + registro de ejecución: [`VALIDACION_PERSISTENCIA.md`](VALIDACION_PERSISTENCIA.md).

```bash
python scripts/verificar_persistencia_e2e.py
# o: pytest tests/test_persistencia_e2e.py -v
```

Cubre DOCUMENTO ok, parcial, PLACA, fallo de BD y tipos JSONB/`raw_html` (portales mockeados; Postgres real).
