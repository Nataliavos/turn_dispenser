# Supabase local con Docker (D-01)

Entorno estándar de persistencia para desarrollo: **Supabase CLI + Docker**.  
El Postgres usable por la app es el del stack Supabase (puerto local **54322** por defecto).

## Decisión de stack (cerrada)

| Opción | ¿Elegida? | Motivo |
|--------|-----------|--------|
| **Supabase CLI** (`supabase start`) | **Sí** | Orquesta Postgres, API, Studio y migraciones oficiales; alineado al PRD. |
| `docker-compose.yml` a mano solo con Postgres | No | Evita divergencia con el stack Supabase y pierde Studio/API locales. |

No se versiona un `docker-compose.yml` propio: el CLI genera/gestiona los contenedores.

**Requisitos:** Docker Engine + [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) (`supabase --version`).

---

## Archivos del repo

```text
supabase/
  config.toml          # project_id = turn_dispenser, puertos locales
  migrations/          # SQL versionado (única convención)
  seed.sql             # opcional; vacío en piloto
  .gitignore           # .temp, .branches, .env locales
scripts/
  apply_local_migrations.sh   # aplica migraciones vía docker exec (workaround)
docs/
  db-schema.md         # entidades, índices, retención
  supabase-local.md    # este documento
```

Variables de ejemplo (sin secretos reales): [`.env.example`](../.env.example).

---

## Arranque (ruta recomendada)

Desde la **raíz del repo**, si Docker puede montar el directorio del proyecto (ext4/local típico):

```bash
# 1) Una sola vez por máquina: Docker en marcha
docker info >/dev/null

# 2) Levantar stack (primera vez descarga imágenes)
supabase start

# 3) Estado + URLs/keys locales
supabase status

# 4) Aplicar migraciones + seed (reset idempotente de esquema local)
supabase db reset
```

Comprobar salud:

```bash
# Postgres
psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -c '\dt public.*'

# o
docker exec -i supabase_db_turn_dispenser psql -U postgres -d postgres -c '\dt public.*'
```

Studio local: URL que imprime `supabase status` (suele ser `http://127.0.0.1:54323`).

### Parada

```bash
supabase stop
# o, si hace falta liberar todo:
supabase stop --no-backup
```

---

## Workaround: repo en disco externo (NTFS / `/media/...`)

Si el clone vive en un volumen que Docker **no puede montar** (p. ej. NTFS bajo `/media/...`), `supabase start` / `supabase db reset` desde el repo fallan al montar `supabase/`.

En ese caso:

1. Mantén un directorio en home (ext4), p. ej. `~/supabase`, con `supabase init` y el mismo `project_id` o uno dedicado.
2. Arranca desde ahí: `cd ~/supabase && supabase start`.
3. Aplica las migraciones **del repo** con:

```bash
# Desde la raíz de turn_dispenser
./scripts/apply_local_migrations.sh

# Si el contenedor no se llama supabase_db_turn_dispenser:
DB_CONTAINER=supabase_db_<project_id> ./scripts/apply_local_migrations.sh
```

El script detecta un contenedor `supabase_db_*` en ejecución si no pasas `DB_CONTAINER`.

Para **reaplicar** la migración inicial tras cambios de esquema (solo local, borra datos):

```bash
DB_CONTAINER=supabase_db_<project_id> ./scripts/apply_local_migrations.sh --reset
```

---

## Variables de entorno

Tras `supabase status`, copia a tu `.env` local (nunca al git):

```bash
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<anon key de status>
SUPABASE_SERVICE_ROLE_KEY=<service_role de status>
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

Plantilla: `.env.example`.  
La app **aún no persiste** en runtime (D-02/D-03); estas vars quedan listas para la capa de repositorios.

---

## Qué no versionar

Cubierto por `.gitignore` / `supabase/.gitignore`:

- `supabase/.temp`, `supabase/.branches`
- `.env`, `.env.local`, keys
- `docker-compose.override.yml`, `.docker/`

Sí se versionan: `config.toml`, `migrations/*.sql`, `seed.sql`.

---

## Criterio de “stack saludable” (aceptación D-01)

1. Contenedor Postgres del stack en `docker ps`.
2. `\dt public.*` muestra `consultas`, `resultados_runt`, `resultados_simit`, `eventos_consulta`.
3. Documentación de esquema en [`db-schema.md`](db-schema.md).
4. Sin columnas de elegibilidad.
