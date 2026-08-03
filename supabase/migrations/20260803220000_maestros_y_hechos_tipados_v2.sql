-- Turn Dispenser — BD v2: maestros + hechos tipados (F-01).
-- Principio: hechos oficiales observados; CERO columnas de elegibilidad
-- (apto / elegible / puede_tramitar / autorización de trámite).
-- No elimina capa A (consultas, resultados_*, eventos_consulta).
-- Diseño: docs/DB_DESIGN_V2.md §4.2–4.3.

-- ---------------------------------------------------------------------------
-- Capa B — Maestros
-- ---------------------------------------------------------------------------

create table public.personas (
  id uuid primary key default gen_random_uuid(),
  tipo_documento text not null,
  numero_documento text not null,
  nombre_completo text,
  estado_persona text,
  numero_inscripcion_runt text,
  -- Texto defensivo: el portal no garantiza date parseable.
  fecha_inscripcion_runt text,
  atributos jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint personas_tipo_numero_uk unique (tipo_documento, numero_documento)
);

create index personas_last_consulta_id_idx on public.personas (last_consulta_id);
create index personas_last_seen_at_idx on public.personas (last_seen_at desc);

create trigger personas_set_updated_at
  before update on public.personas
  for each row
  execute function public.set_updated_at();

comment on table public.personas is
  'Maestro de personas (upsert por tipo+número). Hechos RUNT/SIMIT; sin elegibilidad.';
comment on column public.personas.atributos is
  'Extensión defensiva para campos inestables del portal.';

create table public.vehiculos (
  id uuid primary key default gen_random_uuid(),
  -- Placa normalizada: uppercase, sin espacios ni guiones (app).
  placa text not null,
  atributos jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint vehiculos_placa_uk unique (placa)
);

create index vehiculos_last_consulta_id_idx on public.vehiculos (last_consulta_id);
create index vehiculos_last_seen_at_idx on public.vehiculos (last_seen_at desc);

create trigger vehiculos_set_updated_at
  before update on public.vehiculos
  for each row
  execute function public.set_updated_at();

comment on table public.vehiculos is
  'Maestro de vehículos (upsert por placa normalizada). Sin elegibilidad.';

create table public.persona_vehiculo (
  persona_id uuid not null
    references public.personas (id) on delete cascade,
  vehiculo_id uuid not null
    references public.vehiculos (id) on delete cascade,
  fuente text not null
    check (fuente in ('RUNT', 'SIMIT', 'SISTEMA')),
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  primary key (persona_id, vehiculo_id)
);

create index persona_vehiculo_vehiculo_id_idx
  on public.persona_vehiculo (vehiculo_id);
create index persona_vehiculo_last_consulta_id_idx
  on public.persona_vehiculo (last_consulta_id);

comment on table public.persona_vehiculo is
  'Vínculo N:M persona↔vehículo solo cuando una fuente lo asocia. No inventar vínculos.';

-- ---------------------------------------------------------------------------
-- Capa C — Hechos tipados
-- ---------------------------------------------------------------------------

create table public.licencias (
  id uuid primary key default gen_random_uuid(),
  persona_id uuid not null
    references public.personas (id) on delete cascade,
  numero_licencia text,
  categoria text,
  estado text,
  fecha_expedicion text,
  fecha_vencimiento text,
  atributos jsonb not null default '{}'::jsonb,
  fuente text not null default 'RUNT'
    check (fuente in ('RUNT', 'SIMIT', 'SISTEMA')),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

-- UK: número cuando existe; si no, huella de atributos.
create unique index licencias_persona_numero_uk
  on public.licencias (persona_id, numero_licencia)
  where numero_licencia is not null;

create unique index licencias_persona_atributos_uk
  on public.licencias (persona_id, md5(atributos::text))
  where numero_licencia is null;

create index licencias_persona_id_idx on public.licencias (persona_id);
create index licencias_last_consulta_id_idx on public.licencias (last_consulta_id);

create trigger licencias_set_updated_at
  before update on public.licencias
  for each row
  execute function public.set_updated_at();

comment on table public.licencias is
  'Licencias tipadas (origen típico RUNT), asociadas a persona. Sin elegibilidad.';

create table public.infracciones_runt (
  id uuid primary key default gen_random_uuid(),
  persona_id uuid not null
    references public.personas (id) on delete cascade,
  placa text,
  vehiculo_id uuid
    references public.vehiculos (id) on delete set null,
  descripcion text,
  estado text,
  fecha text,
  valor numeric,
  atributos jsonb not null default '{}'::jsonb,
  fingerprint text not null,
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint infracciones_runt_persona_fingerprint_uk
    unique (persona_id, fingerprint)
);

create index infracciones_runt_persona_id_idx
  on public.infracciones_runt (persona_id);
create index infracciones_runt_vehiculo_id_idx
  on public.infracciones_runt (vehiculo_id);
create index infracciones_runt_last_consulta_id_idx
  on public.infracciones_runt (last_consulta_id);

create trigger infracciones_runt_set_updated_at
  before update on public.infracciones_runt
  for each row
  execute function public.set_updated_at();

comment on table public.infracciones_runt is
  'Hechos del panel RUNT MULTAS E INFRACCIONES. No mezclar con obligaciones_simit.';
comment on column public.infracciones_runt.fingerprint is
  'Hash estable de campos clave para upsert (persona_id, fingerprint).';

create table public.obligaciones_simit (
  id uuid primary key default gen_random_uuid(),
  -- Clave de negocio cuando el portal la expone.
  numero text,
  -- Valor del portal (comparendo, multa, texto libre). Ambos tipos conviven aquí.
  tipo text,
  persona_id uuid
    references public.personas (id) on delete set null,
  vehiculo_id uuid
    references public.vehiculos (id) on delete set null,
  fecha_imposicion text,
  notificacion text,
  secretaria text,
  infraccion text,
  infraccion_descripcion text,
  estado text,
  valor numeric,
  valor_a_pagar numeric,
  atributos jsonb not null default '{}'::jsonb,
  fingerprint text,
  fuente text not null default 'SIMIT'
    check (fuente in ('RUNT', 'SIMIT', 'SISTEMA')),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  activo_en_ultima_consulta boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint obligaciones_simit_clave_negocio_chk
    check (numero is not null or fingerprint is not null)
);

create unique index obligaciones_simit_numero_uk
  on public.obligaciones_simit (numero)
  where numero is not null;

create unique index obligaciones_simit_fingerprint_uk
  on public.obligaciones_simit (fingerprint)
  where numero is null and fingerprint is not null;

create index obligaciones_simit_persona_id_idx
  on public.obligaciones_simit (persona_id);
create index obligaciones_simit_vehiculo_id_idx
  on public.obligaciones_simit (vehiculo_id);
create index obligaciones_simit_last_consulta_id_idx
  on public.obligaciones_simit (last_consulta_id);
create index obligaciones_simit_activo_idx
  on public.obligaciones_simit (activo_en_ultima_consulta)
  where activo_en_ultima_consulta = true;

create trigger obligaciones_simit_set_updated_at
  before update on public.obligaciones_simit
  for each row
  execute function public.set_updated_at();

comment on table public.obligaciones_simit is
  'Comparendos y multas SIMIT en una sola tabla. persona_id y vehiculo_id opcionales. Sin elegibilidad.';
comment on column public.obligaciones_simit.persona_id is
  'Nullable: documento de consulta o cédula en resumen.';
comment on column public.obligaciones_simit.vehiculo_id is
  'Nullable: placa en el hecho o modo PLACA.';
comment on column public.obligaciones_simit.activo_en_ultima_consulta is
  'Útil si un número deja de aparecer en sync por consulta (F-02+).';

create table public.acuerdos_pago_simit (
  id uuid primary key default gen_random_uuid(),
  numero_acuerdo text,
  persona_id uuid
    references public.personas (id) on delete set null,
  vehiculo_id uuid
    references public.vehiculos (id) on delete set null,
  estado text,
  valor numeric,
  atributos jsonb not null default '{}'::jsonb,
  fingerprint text,
  fuente text not null default 'SIMIT'
    check (fuente in ('RUNT', 'SIMIT', 'SISTEMA')),
  last_consulta_id uuid
    references public.consultas (id) on delete set null,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  activo_en_ultima_consulta boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint acuerdos_pago_simit_clave_negocio_chk
    check (numero_acuerdo is not null or fingerprint is not null)
);

create unique index acuerdos_pago_simit_numero_uk
  on public.acuerdos_pago_simit (numero_acuerdo)
  where numero_acuerdo is not null;

create unique index acuerdos_pago_simit_fingerprint_uk
  on public.acuerdos_pago_simit (fingerprint)
  where numero_acuerdo is null and fingerprint is not null;

create index acuerdos_pago_simit_persona_id_idx
  on public.acuerdos_pago_simit (persona_id);
create index acuerdos_pago_simit_vehiculo_id_idx
  on public.acuerdos_pago_simit (vehiculo_id);
create index acuerdos_pago_simit_last_consulta_id_idx
  on public.acuerdos_pago_simit (last_consulta_id);

create trigger acuerdos_pago_simit_set_updated_at
  before update on public.acuerdos_pago_simit
  for each row
  execute function public.set_updated_at();

comment on table public.acuerdos_pago_simit is
  'Acuerdos de pago SIMIT. FKs persona/vehículo opcionales. Sin elegibilidad.';

-- ---------------------------------------------------------------------------
-- Capa A — enriquecer consultas (FKs nullable + contrato schema_version=2)
-- ---------------------------------------------------------------------------

alter table public.consultas
  add column persona_id uuid
    references public.personas (id) on delete set null,
  add column vehiculo_id uuid
    references public.vehiculos (id) on delete set null;

alter table public.consultas
  alter column schema_version set default '2';

create index consultas_persona_id_idx on public.consultas (persona_id);
create index consultas_vehiculo_id_idx on public.consultas (vehiculo_id);
create index consultas_modo_identificador_idx
  on public.consultas (modo, identificador);

comment on column public.consultas.persona_id is
  'FK nullable al maestro resuelto post-parse (F-02). ON DELETE SET NULL.';
comment on column public.consultas.vehiculo_id is
  'FK nullable al maestro resuelto (modo PLACA o placa en hechos). ON DELETE SET NULL.';
comment on column public.consultas.schema_version is
  'Versión del contrato de persistencia de la fila consulta (RF-16). Default 2 = maestros/hechos.';

-- ---------------------------------------------------------------------------
-- RLS — mismo patrón v1 (local/piloto: authenticated; service_role bypasa).
-- ---------------------------------------------------------------------------

alter table public.personas enable row level security;
alter table public.vehiculos enable row level security;
alter table public.persona_vehiculo enable row level security;
alter table public.licencias enable row level security;
alter table public.infracciones_runt enable row level security;
alter table public.obligaciones_simit enable row level security;
alter table public.acuerdos_pago_simit enable row level security;

create policy "personas_select_authenticated"
  on public.personas for select to authenticated using (true);
create policy "personas_insert_authenticated"
  on public.personas for insert to authenticated with check (true);
create policy "personas_update_authenticated"
  on public.personas for update to authenticated using (true) with check (true);

create policy "vehiculos_select_authenticated"
  on public.vehiculos for select to authenticated using (true);
create policy "vehiculos_insert_authenticated"
  on public.vehiculos for insert to authenticated with check (true);
create policy "vehiculos_update_authenticated"
  on public.vehiculos for update to authenticated using (true) with check (true);

create policy "persona_vehiculo_select_authenticated"
  on public.persona_vehiculo for select to authenticated using (true);
create policy "persona_vehiculo_insert_authenticated"
  on public.persona_vehiculo for insert to authenticated with check (true);
create policy "persona_vehiculo_update_authenticated"
  on public.persona_vehiculo for update to authenticated using (true) with check (true);

create policy "licencias_select_authenticated"
  on public.licencias for select to authenticated using (true);
create policy "licencias_insert_authenticated"
  on public.licencias for insert to authenticated with check (true);
create policy "licencias_update_authenticated"
  on public.licencias for update to authenticated using (true) with check (true);

create policy "infracciones_runt_select_authenticated"
  on public.infracciones_runt for select to authenticated using (true);
create policy "infracciones_runt_insert_authenticated"
  on public.infracciones_runt for insert to authenticated with check (true);
create policy "infracciones_runt_update_authenticated"
  on public.infracciones_runt for update to authenticated using (true) with check (true);

create policy "obligaciones_simit_select_authenticated"
  on public.obligaciones_simit for select to authenticated using (true);
create policy "obligaciones_simit_insert_authenticated"
  on public.obligaciones_simit for insert to authenticated with check (true);
create policy "obligaciones_simit_update_authenticated"
  on public.obligaciones_simit for update to authenticated using (true) with check (true);

create policy "acuerdos_pago_simit_select_authenticated"
  on public.acuerdos_pago_simit for select to authenticated using (true);
create policy "acuerdos_pago_simit_insert_authenticated"
  on public.acuerdos_pago_simit for insert to authenticated with check (true);
create policy "acuerdos_pago_simit_update_authenticated"
  on public.acuerdos_pago_simit for update to authenticated using (true) with check (true);

grant select, insert, update, delete on table public.personas to authenticated, service_role;
grant select, insert, update, delete on table public.vehiculos to authenticated, service_role;
grant select, insert, update, delete on table public.persona_vehiculo to authenticated, service_role;
grant select, insert, update, delete on table public.licencias to authenticated, service_role;
grant select, insert, update, delete on table public.infracciones_runt to authenticated, service_role;
grant select, insert, update, delete on table public.obligaciones_simit to authenticated, service_role;
grant select, insert, update, delete on table public.acuerdos_pago_simit to authenticated, service_role;
