# Persistencia (D-02) — conexión y repositorios

Capa Python para leer/escribir hechos oficiales en el **Postgres de Supabase local**.  
No cablea aún GUI/orquestación (eso es **D-03**).

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
```

Cómo levantar el stack y obtener el DSN: [`supabase-local.md`](supabase-local.md).  
Esquema: [`db-schema.md`](db-schema.md).

## API (módulo `repositories/`)

- `Database` / `get_database()` — conexión y `ping()`.
- `ConsultaRepository`:
  - `persistir_resultado_consulta(ResultadoConsulta)` — inserta cabecera + RUNT/SIMIT.
  - `crear_consulta` / `actualizar_estado_consulta`
  - `guardar_resultado_runt` / `guardar_resultado_simit`
  - `agregar_evento` / `listar_eventos`
  - `obtener_por_id`
- Errores: `ConexionPersistenciaError`, `PersistenciaError` (logging vía B-02; sin `print` como canal principal).

## Probar

```bash
# Dependencias
pip install -r requirements.txt -r requirements-dev.txt

# Smoke insert+select (requiere Docker/Supabase + migraciones)
python scripts/smoke_persistencia.py

# Unitarios (sin BD) + integración (skip si no hay Postgres)
pytest tests/test_persistencia_mappers.py tests/test_persistencia_integracion.py -v
```

Si el smoke falla por conexión: confirma `docker ps` (`supabase_db_*`), puerto **54322**, y `./scripts/apply_local_migrations.sh` si hace falta.
