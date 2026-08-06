# Validación de maestros y upserts end-to-end (F-05 / BD v2)

Checklist ejecutable para confirmar criterios de [`DB_DESIGN_V2.md`](DB_DESIGN_V2.md) §12  
contra **Supabase local (Docker)**: N consultas → 1 maestro, hechos tipados, sin elegibilidad.

**Relacionado:** [`persistencia.md`](persistencia.md) · [`VALIDACION_PERSISTENCIA.md`](VALIDACION_PERSISTENCIA.md) (D-04 capa A) · [`db-schema.md`](db-schema.md)

---

## Prerrequisitos

1. Docker + stack Supabase arriba (`docker ps` muestra `supabase_db_*`).
2. Migraciones aplicadas **incluyendo F-01** (`./scripts/apply_local_migrations.sh`).
3. Código con F-02 (escritura de maestros) en la rama bajo prueba.
4. `DATABASE_URL` en `.env` (ver `.env.example`).
5. `pip install -r requirements.txt -r requirements-dev.txt`.
6. `PERSISTENCIA_ENABLED=true` (default).

Los escenarios **no abren Chromium ni portales**: construyen `ResultadoConsulta` mock y pasan por  
`intentar_persistir_resultado` → snapshot (A) + normalización (B/C) en Postgres real.

---

## Cómo repetir (automatizado)

```bash
# Desde la raíz del repo
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
python scripts/verificar_maestros_upsert_e2e.py

# Equivalente:
pytest tests/test_maestros_upsert_e2e.py -v
```

Salida esperada: `RESULTADO GLOBAL: PASS` y 6 tests en verde  
(o *skipped* si no hay Postgres — no cuenta como PASS de estación).

---

## Escenarios

| # | Escenario | Qué se verifica | Automatización |
|---|-----------|-----------------|----------------|
| 1 | 2× DOCUMENTO misma CC | 2 `consultas`, 1 `personas`, licencia upsert | `test_f05_01_*` |
| 2 | 2× PLACA misma placa | 2 `consultas`, 1 `vehiculos`; `tipo_documento` NULL | `test_f05_02_*` |
| 3 | DOCUMENTO + obligación SIMIT | `obligaciones_simit` con `persona_id` + `vehiculo_id`; `raw_html` | `test_f05_03_*` |
| 4 | PLACA `sin_pendientes` | Upsert vehículo; 0 obligaciones de esa corrida | `test_f05_04_*` |
| 5 | Esquema + raw_html | Sin columnas apto/elegible; `raw_html` en `resultados_*` | `test_f05_05_*` |
| 6 | Fallo normalización B/C | Snapshot capa A + hechos en memoria; `persistido=True` | `test_f05_06_*` |

### Criterios por escenario

#### 1 — Dos DOCUMENTO → una persona
- [ ] `count(consultas)` filtrado por documento = 2
- [ ] `count(personas)` por `(CC, numero)` = 1
- [ ] Licencia tipada upsert-eada (1 fila por número de licencia)

#### 2 — Dos PLACA → un vehículo
- [ ] `modo=PLACA`, `tipo_documento` IS NULL en ambas cabeceras
- [ ] `consultas.vehiculo_id` resuelto
- [ ] Una sola fila en `vehiculos` para esa placa

#### 3 — Obligaciones SIMIT
- [ ] Fila en `obligaciones_simit` con número de negocio
- [ ] `persona_id` y `vehiculo_id` no nulos cuando el mock trae placa
- [ ] `raw_html` presente en ambas fuentes

#### 4 — Sin pendientes
- [ ] Resumen SIMIT con `sin_pendientes`
- [ ] Vehículo maestro creado/actualizado
- [ ] Cero obligaciones con `last_consulta_id` = esa corrida

#### 5 — Elegibilidad / evidencia
- [ ] `information_schema`: sin columnas `apto` / `puede_tramitar` / `elegible` / …
- [ ] Tablas v2 `personas`, `vehiculos`, `obligaciones_simit` existen
- [ ] `raw_html` no vacío en snapshot OK

#### 6 — Degradación normalización
- [ ] `persistido is True`, `error_persistencia is None`
- [ ] Filas `resultados_*` con `raw_html` intactas
- [ ] Hechos RUNT/SIMIT siguen en el objeto en memoria

---

## Registro de ejecución

| Campo | Valor |
|-------|--------|
| Fecha (UTC) | 2026-08-06 15:35:54Z |
| Rama | `test/F-05-verificacion-e2e-maestros-upsert` |
| Entorno | Supabase local Docker, Postgres `:54322` |
| Comando | `python scripts/verificar_maestros_upsert_e2e.py` |
| Resultado global | **PASS** |

| Escenario | Veredicto | Notas |
|-----------|-----------|--------|
| 1 Dos DOCUMENTO → 1 persona | **PASS** | Incluye upsert licencia |
| 2 Dos PLACA → 1 vehículo | **PASS** | `tipo_documento` NULL |
| 3 Obligaciones + FKs | **PASS** | `persona_id` + `vehiculo_id` + `raw_html` |
| 4 PLACA sin pendientes | **PASS** | 0 obligaciones de la corrida |
| 5 Elegibilidad + raw_html | **PASS** | Tablas v2 presentes; sin apto/elegible |
| 6 Fallo normalización | **PASS** | Snapshot A intacto; `persistido=True` |

### Bugs bloqueantes encontrados

Ninguno en esta pasada.

### Observaciones

- No sustituye smoke GUI con CAPTCHA real.
- Identificadores de prueba son numéricos únicos / placas `ZZ####` para no chocar entre corridas ni con `upper()` del normalizador.
- D-04 (`VALIDACION_PERSISTENCIA.md`) sigue validando capa A; este doc cubre B/C.

---

## Pasada manual opcional (portales reales)

1. GUI DOCUMENTO misma CC dos veces → SQL: 2 `consultas`, 1 `personas`.
2. GUI PLACA misma placa dos veces → 2 `consultas`, 1 `vehiculos`.
3. Confirmar que **Nueva consulta** no borra filas (F-03).
