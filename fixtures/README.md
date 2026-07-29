# Fixtures HTML para parsers (C-02)

HTML **sintético y anonimizado** para tests offline de `runt_parser` y `simit_parser`.
No contiene datos personales reales.

## Estructura

```text
fixtures/
  runt/
    ok_con_datos.html   # Campos personales + paneles con tablas
    vacio.html          # Sin bloques parseables (sin registro / vacío)
  simit/
    ok_con_datos.html   # Resumen + multaTable con un registro
    sin_pendientes.html # Ceros + mensaje de sin pendientes
```

## Cómo capturar / actualizar fixtures

1. Ejecuta una consulta real en modo debug y guarda el HTML (`raw_html`) de un resultado exitoso o vacío.
2. **Anonimiza** antes de versionar:
   - Nombres → valores ficticios (`PERSONA DE PRUEBA FICTICIA`).
   - Documentos → `1000000001` u otros inventados.
   - Placas → `XYZ999`.
   - Números de comparendo/licencia → prefijos `TEST` / `CMP-TEST-…`.
   - Elimina cookies, tokens, correos, teléfonos y cualquier PII.
3. Conserva la **estructura DOM** que usan los parsers (`label`/`b`, `mat-expansion-panel`, `id="resumenEstadoCuenta"`, `data-label`, etc.).
4. Sustituye el archivo correspondiente en `fixtures/runt/` o `fixtures/simit/`.
5. Corre los tests y ajusta aserciones solo si el contrato de dominio cambió a propósito.

## Cómo correr los tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_runt_parser.py tests/test_simit_parser.py -v
```

Los tests no abren navegador ni usan red.
