# Runbook — estación piloto (E-03)

Guía operativa para **funcionarios de soporte** y quien prepare una estación en CRC/centro.  
No hace falta leer el código fuente.

**Audiencia:** soporte técnico de estación · supervisor de piloto.  
**Alcance:** una estación de prueba (no despliegue multi-sede).  
**Validación previa:** veredicto E-02 en [`PRUEBAS_INTEGRALES.md`](PRUEBAS_INTEGRALES.md) (*LISTO CON MITIGACIONES*).  
Completar §2.6 (prueba con portales) en cada estación antes de considerar el piloto “en vivo”.

---

## 0. Qué hace y qué no hace el sistema

| Hace | No hace |
|------|---------|
| Consulta **RUNT** y/o **SIMIT** y muestra lo que reportan | Decidir si el ciudadano **puede** o **no puede** tramitar |
| Guarda la consulta en Postgres/Supabase local (si está activo) | Calcular “apto”, “elegible” o dictamen de trámite |
| Muestra progreso y errores por fuente | Evadir o resolver el CAPTCHA de RUNT automáticamente |
| Permite **reintentar** la consulta completa sin cerrar la app | Sustituir el criterio del funcionario de ventanilla |

> **Regla de oro del piloto:** Turn Dispenser responde solo a *«¿Qué reportan RUNT y SIMIT?»*.  
> Cualquier decisión de trámite es **humana** y externa a esta aplicación.

---

## 1. Requisitos de máquina

| Requisito | Mínimo recomendado |
|-----------|-------------------|
| SO | Ubuntu 22.04+ (u otro Linux con GUI) o Windows 10/11 |
| Python | 3.10 o superior |
| RAM libre | ≥ 4 GB (modo DOCUMENTO abre 2 Chromium) |
| Disco | ≥ 5 GB libres (imágenes Docker + Chromium) |
| Pantalla / GUI | Obligatoria para mostrador (CAPTCHA RUNT) |
| Red | Salida a Internet hacia portales RUNT y SIMIT |
| Docker | Docker Engine en marcha |
| Supabase CLI | Instalado (`supabase --version`) |
| Navegador Playwright | Chromium vía `python -m playwright install chromium` |

Detalle de instalación Ubuntu: [`../INSTRUCCIONES_UBUNTU.md`](../INSTRUCCIONES_UBUNTU.md).  
Stack de BD: [`supabase-local.md`](supabase-local.md).

---

## 2. Checklist de puesta en marcha (una vez por estación)

Marcar en orden. Tiempo estimado primera vez: 45–90 min.

### 2.1 Software base

- [ ] Python 3.10+ disponible (`python3 --version`)
- [ ] Docker instalado y el daemon responde (`docker info`)
- [ ] Supabase CLI instalado (`supabase --version`)
- [ ] Entorno gráfico activo (para GUI)

### 2.2 Código y dependencias

Desde la raíz del repo (`turn_dispenser/`):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

- [ ] `pip install` sin errores
- [ ] Chromium de Playwright instalado

### 2.3 Persistencia (Supabase local)

```bash
# Docker debe poder montar el directorio del proyecto (preferible disco local ext4).
supabase start
supabase status                    # anotar URL Studio y keys locales
supabase db reset                  # aplica migraciones + seed
```

Si el repo está en NTFS/`/media/...` y Docker no monta:

```bash
# Arrancar stack desde un directorio en home (ver supabase-local.md)
# Luego, desde turn_dispenser:
./scripts/apply_local_migrations.sh
```

- [ ] `docker ps` muestra contenedor `supabase_db_*` healthy
- [ ] Studio abre (suele ser `http://127.0.0.1:54323`)
- [ ] Tablas `consultas`, `resultados_runt`, `resultados_simit`, `eventos_consulta` existen

### 2.4 Configuración `.env`

```bash
cp .env.example .env
# Editar .env — ver sección 3
```

- [ ] `DATABASE_URL` apunta a Postgres local (`…@127.0.0.1:54322/postgres`)
- [ ] `BROWSER_HEADLESS=false`
- [ ] `PERSISTENCIA_ENABLED=true`
- [ ] `OPERADOR` / `ESTACION` rellenados (trazabilidad)
- [ ] `LOG_FILE=logs/turn_dispenser.log` (recomendado en piloto)
- [ ] Carpeta `logs/` creada (`mkdir -p logs`)

### 2.5 Humo de estación

```bash
source .venv/bin/activate
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres   # si no está en .env
python scripts/smoke_persistencia.py
python scripts/verificar_flujo_integral.py
python app_gui.py   # abrir, ver radios Documento/Placa, cerrar
```

- [ ] Smoke persistencia OK
- [ ] Verificación integral: `RESULTADO GLOBAL: PASS` (o documentar fallo)
- [ ] GUI abre sin traceback

### 2.6 Prueba con portales (mitigación E-02)

Usar **datos de prueba del CRC** (no commitear números reales en el repo).

- [ ] GUI DOCUMENTO: CAPTCHA manual → resultados RUNT y/o SIMIT
- [ ] GUI PLACA: solo SIMIT; RUNT en «—»
- [ ] Tras error/parcial: botón **Reintentar consulta** funciona
- [ ] Tras atender: **Nueva consulta** limpia pantalla; **Reintentar** queda deshabilitado; historial BD intacto
- [ ] PLACA/documento **sin pendientes** SIMIT: respuesta en segundos (no ~1–2 min); log `SIMIT: estado sin pendientes detectado`
- [ ] En log aparece `Persistencia: guardada (id=…)` o aviso claro si falló BD

---

## 3. Variables de entorno (estación)

Plantilla: [`.env.example`](../.env.example).

| Variable | Valor piloto típico | Notas |
|----------|---------------------|--------|
| `APP_ENV` | `local` | |
| `DEBUG` | `true` o `false` | `false` reduce ruido en mostrador |
| `LOG_LEVEL` | `INFO` | |
| `LOG_FILE` | `logs/turn_dispenser.log` | Si vacío, solo stderr |
| `BROWSER_HEADLESS` | **`false`** | Obligatorio: CAPTCHA visible |
| `DATABASE_URL` | `postgresql://postgres:postgres@127.0.0.1:54322/postgres` | Debe existir en `.env` (no solo export puntual) |
| `PERSISTENCIA_ENABLED` | `true` | `false` = solo pantalla, no guarda |
| `OPERADOR` | código/nombre corto | Metadato en BD |
| `ESTACION` | p. ej. `CRC-PILOTO-1` | Metadato en BD |
| `APP_VERSION` | tag o fecha | Opcional |
| `SUPABASE_URL` | `http://127.0.0.1:54321` | Referencia local |
| Keys `SUPABASE_*` | de `supabase status` | No empaquetar en instalador de operador |

**Nunca** versionar `.env` con secretos reales.

---

## 4. Arranque y parada diarios

### 4.1 Al iniciar el turno

```bash
# 1) Docker / Supabase
docker info >/dev/null && supabase start   # o verificar que ya está up
docker ps | grep supabase_db

# 2) App
cd /ruta/a/turn_dispenser
source .venv/bin/activate
python app_gui.py
```

### 4.2 Al cerrar el turno

1. Cerrar la ventana de Turn Dispenser.
2. (Opcional) Detener BD si la estación no debe dejar Docker corriendo:

```bash
supabase stop
```

No hace falta `db reset` a diario (borra datos locales).

---

## 5. Flujo del operador (mostrador)

### 5.1 Consulta por documento (RUNT + SIMIT)

1. Seleccionar **Documento de identidad**.
2. Elegir tipo (CC, CE, TI, …) y digitar número.
3. Pulsar **Consultar**.
4. Cuando aparezca el diálogo **Resolver CAPTCHA (RUNT)**: leer la imagen e ingresar el texto → Aceptar.
5. Esperar a que terminen las fuentes (labels `RUNT:` / `SIMIT:`).
6. Revisar el log: bloques RUNT y SIMIT; mensajes de error si los hay.
7. Si falló una o ambas fuentes: leer el diálogo de recuperación y usar **Reintentar consulta** (nuevo CAPTCHA).
8. Para el **siguiente ciudadano**: pulsar **Nueva consulta** (limpia pantalla; no borra historial en BD).

### 5.2 Consulta por placa (solo SIMIT)

1. Seleccionar **Placa del vehículo**.
2. Digitar placa válida (formatos colombianos).
3. **Consultar** — no hay CAPTCHA RUNT.
4. `RUNT: —` es normal en este modo.
5. Al terminar, **Nueva consulta** antes de atender al siguiente.

### 5.3 Nueva consulta / Limpiar (siguiente ciudadano)

Usar cuando termine de atender a una persona y llegue la siguiente **sin** cerrar la app:

1. Pulsar **Nueva consulta**.
2. Se vacían documento/placa, se resetean labels `RUNT:` / `SIMIT:`, se limpia el área de resultados y se deshabilita **Reintentar consulta**.
3. El foco queda en el campo de documento (modo Documento).
4. Digitar el nuevo identificador y **Consultar** de nuevo.

**Importante:** esta acción **no** elimina filas en Postgres; solo limpia el estado de la sesión en pantalla. No interpreta aptitud ni elegibilidad.

### 5.4 Consola (soporte / diagnóstico RUNT)

```bash
python app.py --tipo CC --numero <documento>
```

Pide CAPTCHA por terminal (`captcha.png`). La CLI actual **no** consulta SIMIT.

---

## 6. Cómo interpretar estados (sin elegibilidad)

| Texto en UI / log | Significado operativo |
|-------------------|----------------------|
| `RUNT: OK` / `SIMIT: OK` | Fuente respondió con datos parseables |
| `sin registro` | Portal no mostró registro activo / resultados (hecho, no “rechazo de trámite”) |
| `sin pendientes` | SIMIT sin comparendos/multas/acuerdos pendientes detectados |
| `error` | Fallo operativo (red, timeout, CAPTCHA, portal, parser) |
| `—` / omitido | Fuente no aplica (p. ej. RUNT en modo placa) |
| `estado=parcial` | Una fuente OK y otra con error |
| `Persistencia: guardada` | Se escribió en BD |
| `No se guardó…` | Resultados en pantalla; BD falló — se puede reintentar |

**No interpretar nunca** “OK / sin pendientes / sin registro” como autorización o denegación de un trámite.

La línea *«Multas inferidas (heurística RUNT, no elegibilidad)»* es un **indicador técnico**, no un dictamen.

---

## 7. Fallos comunes y qué hacer

### 7.1 CAPTCHA RUNT

| Síntoma | Qué hacer |
|---------|-----------|
| Diálogo no aparece / app “congelada” | Esperar; no cerrar. Si > 2 min, cancelar, **Reintentar**. Verificar `BROWSER_HEADLESS=false` |
| Texto incorrecto → error RUNT | **Reintentar consulta**; SIMIT pudo haber OK en la corrida previa (parcial) |
| Imagen ilegible | Reintentar (nuevo captcha) |
| Timeout CAPTCHA | Revisar `RUNT_CAPTCHA_TIMEOUT_MS`; reintentar |

**Nunca** automatizar ni bypassear el CAPTCHA.

### 7.2 Red / portales lentos

| Síntoma | Qué hacer |
|---------|-----------|
| `tiempo de espera agotado` en RUNT o SIMIT | Verificar Internet/VPN; reintentar; si persiste, probar el portal en un navegador normal |
| SIMIT “sin pendientes” tarda ~1–2 min | Ya no debería: la espera usa un timeout **único** (F-04). Si vuelve a pasar, reportar con log `SIMIT: estado sin pendientes` / timeout |
| Solo una fuente falla | Usar datos de la fuente OK; reintentar consulta completa si se necesita la otra |
| Ambos fallan | Posible caída de portales o red del CRC — escalar a soporte de sede |

### 7.3 Docker / Supabase

| Síntoma | Qué hacer |
|---------|-----------|
| Aviso «No se guardó en la base de datos» | Resultados siguen en pantalla. Comprobar `docker ps`, `DATABASE_URL`, `supabase start` |
| Contenedor no arranca | `docker info`; reiniciar Docker; `supabase stop` → `supabase start` |
| Tablas faltan | `supabase db reset` **o** `./scripts/apply_local_migrations.sh` (borra/reaplica esquema local) |
| Repo en `/media/...` (NTFS) | Usar workaround de [`supabase-local.md`](supabase-local.md) |

Con `PERSISTENCIA_ENABLED=false` la app **no** intenta guardar (útil si BD está en mantenimiento).

### 7.4 Parsers / HTML del portal cambió

| Síntoma | Qué hacer |
|---------|-----------|
| Consulta “OK” pero campos vacíos o incompletos | Anotar `cid=` del log; capturar evidencia; reportar a desarrollo (posible cambio de HTML) |
| Mensaje de elemento no encontrado / selector | Igual: reintentar una vez; si persiste → incidente a desarrollo |
| Tests offline fallan tras actualizar fixtures | Fuera de mostrador: ver [`../fixtures/README.md`](../fixtures/README.md) |

### 7.5 Validación de entrada

| Síntoma | Qué hacer |
|---------|-----------|
| “Documento inválido” / “Placa inválida” | Corregir formato; la app **no** consultó portales |
| Tipos soportados | CC, CE, TI, RC, PPT, CD, PA |

### 7.6 App / GUI

| Síntoma | Qué hacer |
|---------|-----------|
| No abre GUI | Activar venv; PyQt6 instalado; sesión gráfica |
| Botón Consultar deshabilitado mucho tiempo | Esperar fin de consulta; si colgó, reiniciar app y reportar con logs |
| Reintentar deshabilitado | Solo se habilita tras una consulta previa; **Nueva consulta** lo deshabilita a propósito |
| Quiere atender al siguiente ciudadano | Pulsar **Nueva consulta** (no reiniciar la app; no borra BD) |

---

## 8. Logs e incidentes

### Dónde están

| Origen | Ubicación |
|--------|-----------|
| Archivo (si `LOG_FILE` definido) | `logs/turn_dispenser.log` (o la ruta del `.env`) |
| Consola / terminal | stderr al lanzar `app_gui.py` / `app.py` |
| Panel de la GUI | Área de texto (log de la sesión) |
| BD | Tablas `consultas` / `eventos_consulta` (Studio o `psql`) |

Cada corrida lleva un **correlation id** (`cid=…`) — incluirlo siempre en el reporte.

### Cómo reportar un incidente

Enviar a soporte/desarrollo:

1. Fecha/hora y estación (`ESTACION` / PC).
2. Modo (DOCUMENTO/PLACA), tipo e identificador **parcialmente enmascarado** si es dato personal.
3. `cid=` de la consulta.
4. Texto de error visible (fuente: RUNT/SIMIT/persistencia).
5. Fragmento del log (últimas ~50 líneas de esa corrida).
6. Captura del diálogo CAPTCHA **solo si es necesario** (contiene imagen del portal; tratar como dato sensible).
7. Estado de Docker (`docker ps` filtrado a `supabase`).

Plantilla corta:

```text
Incidente Turn Dispenser
Estación: …
Operador: …
cid: …
Modo: DOCUMENTO|PLACA
Síntoma: …
Acciones ya intentadas: Reintentar / reiniciar Docker / …
```

---

## 9. Escalamiento

| Nivel | Quién | Cuándo |
|-------|-------|--------|
| L1 estación | Operador / supervisor CRC | Reintentos, CAPTCHA, validación de entrada, reinicio app |
| L2 soporte sede | Técnico con acceso a Docker/logs | BD caída, red local, instalación |
| L3 desarrollo | Equipo Turn Dispenser | Parsers rotos, bugs de app, cambios de portal |

No escalar a L3 sin: `cid`, log y descripción de si RUNT, SIMIT o persistencia falló.

---

## 10. Checklist rápido — inicio de jornada

- [ ] Internet OK (abrir RUNT/SIMIT en navegador)
- [ ] `supabase`/Docker up (`docker ps`)
- [ ] `.venv` activado
- [ ] `python app_gui.py` abre
- [ ] Una consulta de humo (placa o documento de prueba)

---

## 11. Documentación relacionada

| Documento | Uso |
|-----------|-----|
| [`.env.example`](../.env.example) | Plantilla de variables |
| [`supabase-local.md`](supabase-local.md) | Arranque/parada Supabase + workaround NTFS |
| [`persistencia.md`](persistencia.md) | Cómo guarda la app |
| [`VALIDACION_PERSISTENCIA.md`](VALIDACION_PERSISTENCIA.md) | Checklist E2E BD capa A (D-04) |
| [`VALIDACION_MAESTROS_UPSERT.md`](VALIDACION_MAESTROS_UPSERT.md) | Checklist E2E maestros/upserts v2 (F-05) |
| [`PRUEBAS_INTEGRALES.md`](PRUEBAS_INTEGRALES.md) | Acta E-02 / go-no-go |
| [`../INSTRUCCIONES_UBUNTU.md`](../INSTRUCCIONES_UBUNTU.md) | Setup Linux detallado |
| [`../README.md`](../README.md) | Visión general del producto |

---

## 12. Alcance del piloto (decisión pendiente)

Por defecto este runbook asume **1 estación**.  
Si el piloto crece a N estaciones: clonar checklist §2 por PC; no compartir el mismo `.env` con keys de producción; coordinar retención de `raw_html` (ver [`db-schema.md`](db-schema.md)).
