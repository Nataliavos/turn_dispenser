# Plan de pruebas — Fase 1

> **Supersedido (E-02):** usar [`docs/PRUEBAS_INTEGRALES.md`](docs/PRUEBAS_INTEGRALES.md)
> como checklist operativo (config, logs, Supabase Docker, reintentos E-01).
> Este documento se conserva como histórico de Fase 1; varios comandos
> (`_consultar_paralelo`, CLI `--modo`) ya no reflejan el código actual.

Batería de pruebas para validar la Fase 1 (orquestación paralela, consola unificada, feedback GUI) y detectar regresiones respecto al comportamiento previo.

**Cuándo ejecutar:** antes de abrir PR de Fase 1, antes de iniciar Fase 2, y tras cualquier cambio en `consulta_controller`, `console_view`, `gui_qt` o `resultado_formatter`.

**Duración estimada:**
- Nivel A (automático / smoke): ~3 min
- Nivel B (orquestación sin portales): ~5 min
- Nivel C (integración manual con RUNT/SIMIT): ~30–45 min

---

## Objetivo

| Verificar | Descripción |
|-----------|-------------|
| **Fase 1.1** | Paralelismo con `ThreadPoolExecutor`; GUI mantiene RUNT en hilo del worker (CAPTCHA Qt). |
| **Fase 1.2** | Consola usa `ConsultaController`; modos `documento` y `placa`; progreso por fuente; formateo compartido. |
| **Fase 1.3** | GUI muestra estado independiente RUNT/SIMIT; resultados parciales no bloquean la consulta. |
| **Regresión** | Lo que ya funcionaba (consulta RUNT, SIMIT, CAPTCHA manual, modos DOCUMENTO/PLACA) sigue operativo. |

---

## Pre-requisitos

```bash
cd /ruta/a/turn_dispenser
source venv/bin/activate          # Linux
# venv\Scripts\activate.bat       # Windows

pip install -r requirements.txt
python -m playwright install chromium
```

- Entorno gráfico activo para pruebas GUI (X11/Wayland).
- Conexión a internet para Nivel C.
- **Datos de prueba acordados** (documentos/placas reales o de prueba del equipo; no commitear en el repo).
- ~4 GB RAM libre recomendados (2 instancias Chromium en modo DOCUMENTO).

### Datos sugeridos (completar localmente)

| ID | Tipo | Identificador | Uso esperado |
|----|------|---------------|--------------|
| D1 | CC | `____________` | Ciudadano con registro RUNT + datos SIMIT |
| D2 | CC | `____________` | Sin registro RUNT y/o sin pendientes SIMIT |
| P1 | Placa | `____________` | Placa con comparendos o multas en SIMIT |
| P2 | Placa | `____________` | Placa sin pendientes |

---

## Nivel A — Smoke (sin red ni portales)

Ejecutar desde la raíz del proyecto con el venv activo.

### A1. Arranque e imports

```bash
python3 -m py_compile app.py app_gui.py \
  controllers/consulta_controller.py \
  views/console_view.py views/gui_qt.py views/resultado_formatter.py

python3 -c "
from controllers.consulta_controller import ConsultaController, _consultar_paralelo
from models.consulta_models import ConsultaParams
from views.resultado_formatter import formatear_resultado_consulta
from views.console_view import _parse_args, _construir_params
print('imports OK')
"
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| A1 | Sin errores de importación ni sintaxis | ☐ |

### A2. CLI — ayuda y validación de argumentos

```bash
# Ayuda
python3 app.py --help

# Modo documento sin args obligatorios → exit != 0
python3 app.py --modo documento 2>&1 | head -1

# Modo placa sin --placa → exit != 0
python3 app.py --modo placa 2>&1 | head -1

# Placa inválida → exit != 0
python3 app.py --modo placa --placa XXX 2>&1 | head -3

# Parseo válido (solo lógica, no consulta)
python3 -c "
from views.console_view import _parse_args, _construir_params
p = _construir_params(_parse_args(['--modo','documento','--tipo','CC','--numero','123']))
assert p.modo == 'DOCUMENTO' and p.identificador == '123'
p2 = _construir_params(_parse_args(['--modo','placa','--placa','ABC123']))
assert p2.modo == 'PLACA' and p2.identificador == 'ABC123'
print('CLI args OK')
"
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| A2.1 | `--help` muestra `--modo`, `--tipo`, `--numero`, `--placa` | ☐ |
| A2.2 | Modo documento sin `--tipo`/`--numero` → mensaje claro y sale | ☐ |
| A2.3 | Modo placa sin `--placa` → mensaje claro y sale | ☐ |
| A2.4 | Placa inválida → mensaje de formatos permitidos | ☐ |
| A2.5 | Script de parseo interno termina con `CLI args OK` | ☐ |

### A3. GUI arranca (sin consultar)

```bash
# Debe abrir ventana; cerrar manualmente con X
python3 app_gui.py
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| A3.1 | Ventana "Turn Dispenser — Consulta RUNT + SIMIT" visible | ☐ |
| A3.2 | Radio "Documento" / "Placa" conmutan campos | ☐ |
| A3.3 | Labels `RUNT: —` y `SIMIT: —` visibles bajo el resumen | ☐ |
| A3.4 | Cierre limpio sin traceback | ☐ |

---

## Nivel B — Orquestación (sin portales)

Prueba que `_consultar_paralelo` y el callback `on_progreso` funcionan sin Playwright.

```bash
python3 - <<'EOF'
import time
from controllers.consulta_controller import _consultar_paralelo

eventos = []

def on_progreso(fuente, estado, mensaje=None):
    eventos.append((fuente, estado, mensaje))

def runt_lento():
    time.sleep(0.3)
    return "runt-ok"

def simit_rapido():
    return "simit-ok"

# Consola: ambos en pool
r, re, s, se = _consultar_paralelo(
    runt_lento, simit_rapido,
    runt_en_hilo_actual=False,
    on_progreso=on_progreso,
)
assert r == "runt-ok" and s == "simit-ok" and re is None and se is None
assert ("SIMIT", "iniciando", None) in eventos
assert ("RUNT", "ok", None) in eventos
assert ("SIMIT", "ok", None) in eventos

# GUI: RUNT en hilo actual
eventos.clear()
r, re, s, se = _consultar_paralelo(
    runt_lento, simit_rapido,
    runt_en_hilo_actual=True,
    on_progreso=on_progreso,
)
assert r == "runt-ok" and s == "simit-ok"
assert eventos.count(("RUNT", "iniciando", None)) == 1

# Error parcial RUNT
def runt_falla():
    raise RuntimeError("fallo runt")

eventos.clear()
r, re, s, se = _consultar_paralelo(
    runt_falla, simit_rapido,
    runt_en_hilo_actual=False,
    on_progreso=on_progreso,
)
assert r is None and "fallo runt" in re
assert s == "simit-ok" and se is None
assert ("RUNT", "error", "fallo runt") in eventos
assert ("SIMIT", "ok", None) in eventos

print("orquestacion OK")
EOF
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| B1 | Script termina con `orquestacion OK` | ☐ |
| B2 | Progreso incluye `iniciando` y `ok`/`error` por fuente | ☐ |
| B3 | Si RUNT falla, SIMIT igual devuelve resultado (no bloqueo) | ☐ |

---

## Nivel C — Integración manual (RUNT + SIMIT)

### C1. Consola — modo documento (RUNT + SIMIT en paralelo)

```bash
python3 app.py --modo documento --tipo CC --numero <D1>
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C1.1 | Mensaje inicial de consulta paralela | ☐ |
| C1.2 | Aparecen `SIMIT: en curso…` y `RUNT: en curso…` (orden puede variar) | ☐ |
| C1.3 | Se guarda `captcha.png` y pide texto por stdin | ☐ |
| C1.4 | Tras CAPTCHA correcto: `RUNT: ok` y/o `SIMIT: ok` | ☐ |
| C1.5 | Bloques `══════════ RUNT ══════════` y `══════════ SIMIT ══════════` en salida | ☐ |
| C1.6 | Campos clave RUNT: nombre, estado licencia, secciones | ☐ |
| C1.7 | Campos clave SIMIT: resumen, comparendos/acuerdos si aplican | ☐ |

**Paralelismo (observación):** mientras resuelves CAPTCHA, SIMIT debería avanzar; si SIMIT termina antes, verás `SIMIT: ok` antes de completar RUNT.

---

### C2. Consola — modo placa (solo SIMIT)

```bash
python3 app.py --modo placa --placa <P1>
```

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C2.1 | No aparece CAPTCHA ni mensajes RUNT | ☐ |
| C2.2 | Solo `SIMIT: en curso…` → `SIMIT: ok` | ☐ |
| C2.3 | Bloque SIMIT con datos coherentes con el portal | ☐ |
| C2.4 | No hay sección RUNT en la salida | ☐ |

---

### C3. GUI — modo documento

1. `python3 app_gui.py`
2. Documento → tipo CC → número `<D1>` → **Consultar**
3. Resolver CAPTCHA en el diálogo modal

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C3.1 | UI no se congela durante la consulta | ☐ |
| C3.2 | `Consulta en curso…` en resumen | ☐ |
| C3.3 | `RUNT: consultando…` y `SIMIT: consultando…` (actualización independiente) | ☐ |
| C3.4 | Diálogo CAPTCHA modal sobre la ventana principal | ☐ |
| C3.5 | Tras completar: estados `RUNT: ok` / `SIMIT: ok` (o `error` si aplica) | ☐ |
| C3.6 | Resumen final: `Consulta completada` o mensaje parcial explícito | ☐ |
| C3.7 | Log con secciones RUNT y SIMIT formateadas | ☐ |
| C3.8 | Botón **Consultar** se rehabilita al terminar | ☐ |

---

### C4. GUI — modo placa

1. Placa → `<P1>` → **Consultar**

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C4.1 | `RUNT: no aplica` desde el inicio | ☐ |
| C4.2 | `SIMIT: consultando…` → `SIMIT: ok` | ☐ |
| C4.3 | Placa inválida (ej. `XXX`) → QMessageBox de validación, sin consulta | ☐ |
| C4.4 | Solo resultados SIMIT en el log | ☐ |

---

### C5. Regresión — casos sin registro / sin pendientes

Repetir **C1** con `<D2>` y **C2** con `<P2>` si están disponibles.

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C5.1 | RUNT: `Sin registro ACTIVO en RUNT` cuando aplique | ☐ |
| C5.2 | SIMIT: `No se detectaron resultados en SIMIT` cuando aplique | ☐ |
| C5.3 | Consulta termina sin crash; estados finales reflejan ok/error por fuente | ☐ |

---

### C6. Resultado parcial (opcional, difícil de forzar)

Intentar provocar fallo en una sola fuente (red intermitente, CAPTCHA incorrecto una vez, timeout).

| # | Resultado esperado | OK |
|---|-------------------|-----|
| C6.1 | Una fuente en `error`, la otra en `ok` | ☐ |
| C6.2 | Resumen GUI: `Consulta parcial: …` | ☐ |
| C6.3 | Log/consola muestra datos de la fuente exitosa + error de la fallida | ☐ |
| C6.4 | La app no cuelga; botón Consultar usable de nuevo | ☐ |

---

## Checklist de regresión (comportamiento previo)

| Área | Antes de Fase 1 | Debe seguir igual | OK |
|------|-----------------|-------------------|-----|
| CAPTCHA RUNT | Manual en GUI y consola | Sin automatización ni bypass | ☐ |
| Consulta RUNT por documento | Funcional en GUI | Datos parseados en log | ☐ |
| Consulta SIMIT por documento | Funcional en GUI (paralelo) | Datos SIMIT presentes | ☐ |
| Consulta SIMIT por placa | Funcional en GUI | Sin intento RUNT | ☐ |
| Validación placa | Formatos colombianos | Rechazo en GUI y consola | ☐ |
| Tipos documento GUI | CC, CE, TI, RC, PPT | Combo intacto | ☐ |
| `raw_html` en modelos | Presente en controladores | Verificar en debug si se usa | ☐ |

---

## Criterios de aceptación Fase 1 (salida)

Marcar **APTO para Fase 2** solo si se cumple todo lo siguiente:

- [ ] Nivel A: 100 % en verde
- [ ] Nivel B: 100 % en verde
- [ ] Nivel C: C1, C2, C3, C4 y C5 completados sin fallos críticos
- [ ] En modo DOCUMENTO, RUNT y SIMIT arrancan casi al mismo tiempo (GUI y consola)
- [ ] Errores parciales visibles y no bloquean el resultado de la otra fuente
- [ ] Consola nueva CLI (`--modo documento|placa`) operativa; la CLI antigua (`--tipo --numero` sola) **ya no aplica** — documentar el cambio si alguien tenía scripts viejos

---

## Comandos rápidos — resumen

```bash
# Smoke completo Nivel A + B
python3 -m py_compile app.py app_gui.py controllers/consulta_controller.py views/*.py
python3 -c "from views.console_view import _parse_args, _construir_params; print('OK')"
# (pegar script Nivel B)

# Integración
python3 app.py --modo documento --tipo CC --numero <D1>
python3 app.py --modo placa --placa <P1>
python3 app_gui.py
```

---

## Plantilla — Test plan para Pull Request

Copiar en la descripción del PR de Fase 1:

```markdown
## Summary
- Refactor paralelismo con ThreadPoolExecutor en ConsultaController
- Consola unificada con ConsultaController (modos documento/placa)
- Feedback GUI independiente RUNT/SIMIT + formateo compartido

## Test plan
- [ ] Nivel A smoke (imports, CLI, GUI arranque) — ver PRUEBAS_FASE1.md
- [ ] Nivel B orquestación sin portales
- [ ] Consola documento: RUNT+SIMIT paralelo + CAPTCHA + progreso
- [ ] Consola placa: solo SIMIT
- [ ] GUI documento: estados RUNT/SIMIT + CAPTCHA + resultados
- [ ] GUI placa: RUNT no aplica + validación placa
- [ ] Regresión: sin registro / sin pendientes
- [ ] (Opcional) Resultado parcial una fuente falla

## Notas
- Requiere Chromium instalado y datos de prueba locales
- CLI anterior `--tipo/--numero` reemplazada por `--modo documento --tipo --numero`
```

---

## Riesgos conocidos (no bloquean Fase 1 si se documentan)

| Riesgo | Cómo detectarlo en pruebas |
|--------|----------------------------|
| RAM insuficiente con 2 Chromium | C1/C3 lentos o OOM — anotar RAM libre |
| Portal RUNT/SIMIT caído o lento | Timeout; repetir en otro momento |
| CAPTCHA incorrecto | RUNT error; SIMIT debe seguir ok |
| HTML del portal cambió | Datos vacíos o parser incompleto — es scope Fase 2, no Fase 1 |

---

## Registro de ejecución

| Fecha | Ejecutor | Nivel A | Nivel B | Nivel C | APTO Fase 2 |
|-------|----------|---------|---------|---------|-------------|
| | | ☐ | ☐ | ☐ | ☐ |
