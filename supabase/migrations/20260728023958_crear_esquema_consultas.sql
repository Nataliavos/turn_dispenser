-- Turn Dispenser — esquema inicial de persistencia (hechos oficiales).
-- Principio: guardar lo reportado por RUNT/SIMIT, sin columnas de elegibilidad.
-- Alineado a models/ (C-01). JSONB + raw_html toleran evolución de parsers (RF-16).

-- ---------------------------------------------------------------------------
-- Utilidad: updated_at automático
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- consultas — cabecera de cada corrida (ResultadoConsulta / ConsultaParams)
-- ---------------------------------------------------------------------------
create table public.consultas (
  id uuid primary key default gen_random_uuid(),
  -- Correlation id de logging / trazabilidad (ResultadoConsulta.correlation_id)
  correlation_id text,
  modo text not null
    check (modo in ('DOCUMENTO', 'PLACA')),
  identificador text not null,
  tipo_documento text,
  -- ok | parcial | error | omitido | en_progreso
  estado text not null default 'en_progreso'
    check (estado in ('en_progreso', 'ok', 'parcial', 'error', 'omitido')),
  operador text,
  estacion text,
  app_version text,
  -- Versión del contrato de persistencia de la app (RF-16)
  schema_version text not null default '1',
  iniciado_en timestamptz,
  finalizado_en timestamptz,
  duracion_ms integer
    check (duracion_ms is null or duracion_ms >= 0),
  error_runt text,
  error_simit text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint consultas_documento_requiere_tipo
    check (
      (modo = 'DOCUMENTO' and tipo_documento is not null)
      or (modo = 'PLACA')
    )
);

create index consultas_identificador_idx on public.consultas (identificador);
create index consultas_correlation_id_idx on public.consultas (correlation_id);
create index consultas_created_at_idx on public.consultas (created_at desc);
create index consultas_modo_estado_idx on public.consultas (modo, estado);

create trigger consultas_set_updated_at
  before update on public.consultas
  for each row
  execute function public.set_updated_at();

comment on table public.consultas is
  'Cabecera de cada consulta ejecutada (documento o placa). Sin lógica de elegibilidad.';
comment on column public.consultas.schema_version is
  'Versión del contrato de persistencia de la fila consulta (RF-16).';
comment on column public.consultas.correlation_id is
  'Id de correlación de logs/UI (ResultadoConsulta.correlation_id).';

-- ---------------------------------------------------------------------------
-- resultados_runt — 1:1 con consulta (ResultadoRunt; omitido en modo PLACA)
-- ---------------------------------------------------------------------------
create table public.resultados_runt (
  id uuid primary key default gen_random_uuid(),
  consulta_id uuid not null unique
    references public.consultas (id) on delete cascade,
  -- Contrato del payload secciones (SCHEMA_VERSION_RUNT)
  schema_version text not null default '1',
  -- ok | parcial | error | omitido
  estado text not null
    check (estado in ('ok', 'parcial', 'error', 'omitido')),
  sin_registro boolean not null default false,
  nombre text,
  estado_licencia text,
  tipo_documento text,
  numero_documento text,
  estado_persona text,
  numero_inscripcion text,
  fecha_inscripcion text,
  -- Heurística del parser (tiene_multas_inferidas). NO es dictamen de negocio.
  tiene_multas_inferidas boolean,
  secciones jsonb not null default '{}'::jsonb,
  raw_html text,
  error_mensaje text,
  duracion_ms integer
    check (duracion_ms is null or duracion_ms >= 0),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index resultados_runt_consulta_id_idx on public.resultados_runt (consulta_id);

create trigger resultados_runt_set_updated_at
  before update on public.resultados_runt
  for each row
  execute function public.set_updated_at();

comment on table public.resultados_runt is
  'Hechos observados en RUNT. Mapear a models/runt_models.ResultadoRunt.';
comment on column public.resultados_runt.raw_html is
  'Evidencia técnica para depuración/re-parseo. Contiene datos personales; retención local recomendada ≤ 30 días en piloto.';
comment on column public.resultados_runt.tiene_multas_inferidas is
  'Campo derivado/heurístico del parser; no usar como regla de elegibilidad.';
comment on column public.resultados_runt.schema_version is
  'Versión del contrato de secciones (SCHEMA_VERSION_RUNT).';

-- ---------------------------------------------------------------------------
-- resultados_simit — 1:1 con consulta (ResultadoSimit)
-- ---------------------------------------------------------------------------
create table public.resultados_simit (
  id uuid primary key default gen_random_uuid(),
  consulta_id uuid not null unique
    references public.consultas (id) on delete cascade,
  schema_version text not null default '1',
  estado text not null
    check (estado in ('ok', 'parcial', 'error', 'omitido')),
  sin_registro boolean not null default false,
  resumen jsonb,
  comparendos_multas jsonb not null default '[]'::jsonb,
  acuerdos_pago jsonb not null default '[]'::jsonb,
  total_comparendos_multas jsonb,
  total_acuerdos_pago jsonb,
  datos_raw jsonb not null default '{}'::jsonb,
  raw_html text,
  error_mensaje text,
  duracion_ms integer
    check (duracion_ms is null or duracion_ms >= 0),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index resultados_simit_consulta_id_idx on public.resultados_simit (consulta_id);

create trigger resultados_simit_set_updated_at
  before update on public.resultados_simit
  for each row
  execute function public.set_updated_at();

comment on table public.resultados_simit is
  'Hechos observados en SIMIT. Listas JSONB alineadas a models/simit_models.py.';
comment on column public.resultados_simit.raw_html is
  'Evidencia técnica para depuración/re-parseo. Contiene datos personales; retención local recomendada ≤ 30 días en piloto.';
comment on column public.resultados_simit.schema_version is
  'Versión del contrato tipado SIMIT (SCHEMA_VERSION_SIMIT).';

-- ---------------------------------------------------------------------------
-- eventos_consulta — timeline de automatización (auditoría / soporte)
-- ---------------------------------------------------------------------------
create table public.eventos_consulta (
  id uuid primary key default gen_random_uuid(),
  consulta_id uuid not null
    references public.consultas (id) on delete cascade,
  fuente text
    check (fuente is null or fuente in ('RUNT', 'SIMIT', 'SISTEMA')),
  nivel text not null default 'info'
    check (nivel in ('debug', 'info', 'warning', 'error')),
  codigo text,
  mensaje text not null,
  detalle jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now())
);

create index eventos_consulta_consulta_id_idx
  on public.eventos_consulta (consulta_id, created_at);

comment on table public.eventos_consulta is
  'Timeline de la corrida para soporte y auditoría (RF-19 / modelo de eventos).';

-- ---------------------------------------------------------------------------
-- RLS — habilitado; políticas permisivas solo para entorno local/piloto.
-- En producción se restringirán por estación/rol (D-02+).
-- ---------------------------------------------------------------------------
alter table public.consultas enable row level security;
alter table public.resultados_runt enable row level security;
alter table public.resultados_simit enable row level security;
alter table public.eventos_consulta enable row level security;

create policy "consultas_select_authenticated"
  on public.consultas for select
  to authenticated
  using (true);

create policy "consultas_insert_authenticated"
  on public.consultas for insert
  to authenticated
  with check (true);

create policy "consultas_update_authenticated"
  on public.consultas for update
  to authenticated
  using (true)
  with check (true);

create policy "resultados_runt_select_authenticated"
  on public.resultados_runt for select
  to authenticated
  using (true);

create policy "resultados_runt_insert_authenticated"
  on public.resultados_runt for insert
  to authenticated
  with check (true);

create policy "resultados_runt_update_authenticated"
  on public.resultados_runt for update
  to authenticated
  using (true)
  with check (true);

create policy "resultados_simit_select_authenticated"
  on public.resultados_simit for select
  to authenticated
  using (true);

create policy "resultados_simit_insert_authenticated"
  on public.resultados_simit for insert
  to authenticated
  with check (true);

create policy "resultados_simit_update_authenticated"
  on public.resultados_simit for update
  to authenticated
  using (true)
  with check (true);

create policy "eventos_consulta_select_authenticated"
  on public.eventos_consulta for select
  to authenticated
  using (true);

create policy "eventos_consulta_insert_authenticated"
  on public.eventos_consulta for insert
  to authenticated
  with check (true);

-- Acceso local vía service_role / Postgres bypasa RLS (CLI, repositorios con service key).
-- Políticas anon deshabilitadas a propósito: la app de escritorio no debe escribir con anon abierta.

grant usage on schema public to anon, authenticated, service_role;

grant select, insert, update, delete on table public.consultas to authenticated, service_role;
grant select, insert, update, delete on table public.resultados_runt to authenticated, service_role;
grant select, insert, update, delete on table public.resultados_simit to authenticated, service_role;
grant select, insert, update, delete on table public.eventos_consulta to authenticated, service_role;
