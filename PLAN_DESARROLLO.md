# Plan de desarrollo (ARCHIVADO)

> **Estado:** supersedido.  
> **No usar este documento como fuente de verdad.**

La especificación vigente del producto y del plan de implementación está en:

**[`docs/product-requirements-document.md`](docs/product-requirements-document.md)**

---

## Por qué se archiva

Este archivo describía un estado anterior del repo (p. ej. consola “sin paralelo”, checklist de Fase 0/1 incompleto, `pip freeze` como práctica de deps). Tras A-01/A-02 y la adopción del PRD, **contradecía** el código y generaba decisiones erróneas.

---

## Estado real resumido (referencia rápida)

| Área | Estado en código (aprox.) |
|------|---------------------------|
| RUNT Playwright + CAPTCHA manual | Implementado |
| SIMIT Playwright + parser | Implementado |
| GUI DOCUMENTO (RUNT∥SIMIT) / PLACA (SIMIT) | Implementado (`ConsultaController`) |
| Consola | Solo RUNT por documento (`app.py`); aún no unificada con `ConsultaController` |
| Config / logging profesional | Pendiente |
| Persistencia Supabase + Docker | Pendiente (decisión de stack en el PRD) |
| Tests automatizados de parsers | Pendiente |
| Reglas de elegibilidad | Fuera de alcance |

Detalle y fases: ver el PRD.  
Uso diario: [`README.md`](README.md) y [`WORKFLOW.md`](WORKFLOW.md).

---

## Contenido histórico

El texto largo original de fases 0–4 se omitió a propósito para evitar que se tome como plan activo. Si necesitas el historial, está en el historial de Git de este archivo antes de A-03.
