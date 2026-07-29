# Validación de persistencia end-to-end (D-04)

Checklist ejecutable para confirmar RF-13 / RF-14 contra **Supabase local (Docker)**.  
No valida reglas de elegibilidad ni piloto en CRC.

**Relacionado:** [`persistencia.md`](persistencia.md) · [`db-schema.md`](db-schema.md) · [`supabase-local.md`](supabase-local.md)

---

## Prerrequisitos

1. Docker + stack Supabase arriba (`docker ps` muestra `supabase_db_*`).
2. Migraciones aplicadas (`supabase db reset` o `./scripts/apply_local_migrations.sh`).
3. `DATABASE_URL` en `.env` (ver `.env.example`).
4. `pip install -r requirements.txt -r requirements-dev.txt`.
5. `PERSISTENCIA_ENABLED=true` (default).

Los escenarios automatizados **no abren Chromium ni portales**: mockean RUNT/SIMIT y escriben en Postgres real.  
Para una pasada manual con GUI + CAPTCHA, usar la sección «Pasada manual opcional» al final.

---

## Cómo repetir (automatizado)

```bash
# Desde la raíz del repo
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
python scripts/verificar_persistencia_e2e.py

# Equivalente:
pytest tests/test_persistencia_e2e.py -v
```

Salida esperada: `RESULTADO GLOBAL: PASS` y 5 tests en verde.

---

## Escenarios

| # | Escenario | Qué se verifica | Automatización |
|---|-----------|-----------------|----------------|
| 1 | DOCUMENTO ok (RUNT+SIMIT) | Cabecera `ok`, ambas fuentes, `raw_html`, evento | `test_e2e_01_*` |
| 2 | DOCUMENTO parcial | `estado=parcial`, RUNT OK + error SIMIT persistido | `test_e2e_02_*` |
| 3 | PLACA ok | Solo SIMIT; **sin** fila `resultados_runt` | `test_e2e_03_*` |
| 4 | Fallo de persistencia | DSN inválido → `error_persistencia`; hechos en memoria | `test_e2e_04_*` |
| + | JSONB / `raw_html` | Tipos JSON en Postgres; sin columnas de elegibilidad | `test_e2e_json_*` + assert en #1 |

### Criterios por escenario

#### 1 — DOCUMENTO ok
- [ ] `ResultadoConsulta.persistido is True` y `consulta_db_id` UUID
- [ ] Fila en `consultas` con `modo=DOCUMENTO`, `estado=ok`
- [ ] Filas en `resultados_runt` y `resultados_simit` con `raw_html` no vacío
- [ ] Al menos un evento en `eventos_consulta`
- [ ] No existen columnas `apto` / `puede_tramitar` / `elegible` en tablas de app

#### 2 — DOCUMENTO parcial
- [ ] `estado_global=parcial` y mismo en BD
- [ ] `error_simit` (o `error_mensaje` SIMIT) presente
- [ ] Hechos RUNT (`nombre` / `raw_html`) guardados

#### 3 — PLACA ok
- [ ] `modo=PLACA`, SIMIT persistido
- [ ] `count(*)` en `resultados_runt` para esa consulta = 0

#### 4 — Fallo de BD / Docker
- [ ] `persistido is False` y mensaje en `error_persistencia`
- [ ] `resultado_runt` / `resultado_simit` siguen en memoria
- [ ] Comportamiento UI esperado (manual): resultados visibles + aviso; no crash

---

## Registro de ejecución

| Campo | Valor |
|-------|--------|
| Fecha (UTC) | 2026-07-29 22:40:23Z |
| Rama | `test/D-04-verificar-persistencia-end-to-end` |
| Entorno | Supabase local Docker (`supabase_db_nataliavos`), Postgres `:54322` |
| Comando | `python scripts/verificar_persistencia_e2e.py` |
| Resultado global | **PASS** |

| Escenario | Veredicto | Notas |
|-----------|-----------|--------|
| 1 DOCUMENTO ok | **PASS** | Controllers mockeados; filas + `raw_html` OK |
| 2 DOCUMENTO parcial | **PASS** | SIMIT error + RUNT hechos en BD |
| 3 PLACA ok | **PASS** | Sin fila RUNT |
| 4 Fallo persistencia | **PASS** | DSN puerto `1`; resultados en memoria |
| JSONB / esquema | **PASS** | `pg_typeof` json*; sin columnas de elegibilidad |

### Bugs bloqueantes encontrados

Ninguno en esta pasada.

### Observaciones

- La automatización cubre el camino `ConsultaController` → `intentar_persistir_resultado` → Postgres.
- No sustituye una corrida GUI con CAPTCHA real (opcional abajo).
- CLI RUNT-only persiste solo hechos RUNT (documentado en D-03); escenarios 1–3 usan el orquestador completo.

---

## Pasada manual opcional (GUI + portales)

Usar solo si se quiere evidencia con HTML real de RUNT/SIMIT.

1. `python app_gui.py` con Docker arriba y `PERSISTENCIA_ENABLED=true`.
2. DOCUMENTO: completar CAPTCHA; anotar `Persistencia: guardada (id=…)` en el log.
3. Verificar en Studio o `psql`:

```sql
select id, modo, estado, identificador from public.consultas order by created_at desc limit 5;
select consulta_id, left(raw_html, 40) from public.resultados_runt order by created_at desc limit 3;
```

4. Detener Docker / poner `DATABASE_URL` inválida: repetir consulta → resultados en pantalla + diálogo «No se guardó…».
5. Anotar fecha/operador y veredicto en una fila nueva de «Registro de ejecución».

---

## Ausencia de lógica de elegibilidad

Confirmado en esquema (`information_schema`) y por diseño de modelos/repositorios: no se persiste ni calcula `apto` / `puede_tramitar` / scores de trámite.
