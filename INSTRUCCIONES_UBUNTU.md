# Guía: ejecutar turn_dispenser en Ubuntu Linux

Proyecto: **turn_dispenser** (consulta RUNT con Playwright + PyQt6)

---

## Requisitos previos

- **Ubuntu** (o derivado: Linux Mint, etc.)
- **Python 3.10 o superior**
- **Conexión a internet**
- Para la **GUI**: entorno gráfico (X11/Wayland) y librerías Qt

---

## 1. Comprobar Python

Abre una terminal y verifica:

```bash
python3 --version
```

Si no tienes Python 3.10+, instálalo:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

---

## 2. Ir a la carpeta del proyecto

```bash
cd /ruta/donde/esté/turn_dispenser
```

Ejemplo:

```bash
cd ~/TESLA/turn_dispenser
# o
cd /media/nataliavos/PROGRAMAS/TESLA/turn_dispenser
```

---

## 3. Crear entorno virtual (solo la primera vez)

```bash
python3 -m venv venv
```

---

## 4. Activar el entorno virtual

En Linux/Ubuntu se usa `source` (no `activate.bat` como en Windows):

```bash
source venv/bin/activate
```

Si está bien, verás algo como:

```bash
(venv) usuario@equipo:~/.../turn_dispenser$
```

---

## 5. Actualizar pip e instalar dependencias

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si la **GUI** da error por PyQt6, instálalo aparte:

```bash
pip install PyQt6
```

---

## 6. Instalar Chromium para Playwright

```bash
python -m playwright install chromium
```

En Ubuntu a veces hacen falta dependencias del sistema para Chromium. Si `playwright install` falla, ejecuta:

```bash
python -m playwright install-deps chromium
```

(Si pide contraseña de `sudo`, introdúcela cuando lo pida.)

Luego repite:

```bash
python -m playwright install chromium
```

---

## 7. Ejecutar el programa

### Con interfaz gráfica (recomendado)

```bash
python app_gui.py
```

### Solo consola

```bash
python app.py --tipo CC --numero 1017259440
```

Sustituye `CC` y `1017259440` por el tipo y número de documento que quieras consultar.

---

## 8. CAPTCHA

- **Consola**: se guarda `captcha.png` y la terminal pide que escribas el texto.
- **GUI**: se abre una ventana con la imagen y un campo para escribir el texto del CAPTCHA.

---

## 9. Desactivar el entorno virtual (opcional)

Cuando termines:

```bash
deactivate
```

---

## Resumen rápido (copiar y pegar)

```bash
cd /media/nataliavos/PROGRAMAS/TESLA/turn_dispenser
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install PyQt6
python -m playwright install chromium
python app_gui.py
```

(Ajusta la ruta del `cd` a tu carpeta del proyecto.)

---

## Problemas frecuentes en Ubuntu

| Problema | Solución |
|----------|----------|
| `python: command not found` | Usa `python3` en lugar de `python`. |
| Error al importar PyQt6 | `pip install PyQt6` y, si hace falta, `sudo apt install libxcb-cursor0 libxkbcommon-x11-0`. |
| Playwright no abre Chromium | Ejecuta `python -m playwright install-deps chromium` (con `sudo` si lo pide) y luego `python -m playwright install chromium`. |
| No se muestra la ventana GUI | Comprueba que tienes sesión gráfica (no solo SSH sin X11). En SSH con X11: `ssh -X` o `ssh -Y`. |

---

*Este proyecto no evade mecanismos de seguridad. El CAPTCHA se resuelve manualmente.*
