#!/usr/bin/env bash
# Aplica migraciones de supabase/migrations al Postgres local de Supabase.
#
# Uso (desde la raíz del repo):
#   ./scripts/apply_local_migrations.sh
#   ./scripts/apply_local_migrations.sh --reset   # dropea tablas del esquema app y reaplica
#
# Nota: si el proyecto vive en un disco externo (/media/...), Docker puede
# no poder montar la ruta y `supabase start` / `supabase db reset` fallan.
# Este script aplica el SQL vía `docker exec` al contenedor de Postgres.
#
# Contenedor: DB_CONTAINER o auto-detección de supabase_db_*.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_DIR="${ROOT_DIR}/supabase/migrations"
RESET=0

for arg in "$@"; do
  case "${arg}" in
    --reset) RESET=1 ;;
    -h|--help)
      echo "Uso: $0 [--reset]"
      echo "  --reset  Elimina tablas públicas de la app y el registro de migraciones, luego reaplica."
      exit 0
      ;;
    *)
      echo "Argumento desconocido: ${arg}" >&2
      exit 1
      ;;
  esac
done

detect_db_container() {
  local names
  names="$(docker ps --format '{{.Names}}' | grep -E '^supabase_db_' || true)"
  if [[ -z "${names}" ]]; then
    return 1
  fi
  # Preferir project_id del repo si está corriendo
  if echo "${names}" | grep -qx 'supabase_db_turn_dispenser'; then
    echo 'supabase_db_turn_dispenser'
    return 0
  fi
  # Si hay exactamente uno, usarlo
  if [[ "$(echo "${names}" | wc -l)" -eq 1 ]]; then
    echo "${names}"
    return 0
  fi
  echo "Hay varios contenedores supabase_db_*. Define DB_CONTAINER=..." >&2
  echo "${names}" >&2
  return 1
}

DB_CONTAINER="${DB_CONTAINER:-}"
if [[ -z "${DB_CONTAINER}" ]]; then
  DB_CONTAINER="$(detect_db_container)" || {
    echo "No hay contenedor supabase_db_* en ejecución."
    echo "Levanta Supabase (supabase start) e intenta de nuevo."
    exit 1
  }
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${DB_CONTAINER}"; then
  echo "No está corriendo el contenedor '${DB_CONTAINER}'."
  exit 1
fi

if [[ ! -d "${MIGRATIONS_DIR}" ]]; then
  echo "No existe ${MIGRATIONS_DIR}"
  exit 1
fi

echo "Usando contenedor: ${DB_CONTAINER}"

psql_db() {
  docker exec -i "${DB_CONTAINER}" psql -U postgres -d postgres "$@"
}

if [[ "${RESET}" -eq 1 ]]; then
  echo "Reset local: dropeando tablas de la app..."
  psql_db <<'SQL'
drop table if exists public.eventos_consulta cascade;
drop table if exists public.resultados_runt cascade;
drop table if exists public.resultados_simit cascade;
drop table if exists public.consultas cascade;
drop function if exists public.set_updated_at() cascade;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
  version text primary key,
  statements text[],
  name text
);
delete from supabase_migrations.schema_migrations
  where version like '20260728%'
     or name like '%crear_esquema%'
     or name like '%consultas%';
SQL
fi

psql_db <<'SQL'
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (
  version text primary key,
  statements text[],
  name text
);
SQL

shopt -s nullglob
for file in "${MIGRATIONS_DIR}"/*.sql; do
  base="$(basename "${file}" .sql)"
  version="${base%%_*}"
  name="${base#*_}"

  already="$(psql_db -tAc \
    "select 1 from supabase_migrations.schema_migrations where version = '${version}' limit 1;")"

  if [[ "${already}" == "1" ]]; then
    echo "Skip (ya aplicada): ${base}"
    continue
  fi

  echo "Aplicando: ${base}"
  psql_db < "${file}"
  psql_db -c \
    "insert into supabase_migrations.schema_migrations (version, name) values ('${version}', '${name}');"
done

echo "Migraciones al día."
psql_db -c '\dt public.*'
