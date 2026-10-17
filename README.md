# Noticias de la Ciberpedia

Cada día (y cada 5 horas, vía la tarea programada que actualiza el artefacto), GitHub Actions ejecuta `generar_noticias.py`, que junta noticias reales de varias fuentes y tus propios mensajes, y guarda el resultado en `noticias.json`.

## Fuentes

Noticias dinámicas (cambian solas en cada ejecución):

- **INCIBE-CERT** — avisos de alerta temprana (RSS oficial del CERT español).
- **Hispasec «una-al-día»** — noticias de seguridad en español, fuente clásica y fiable (RSS).
- **ciberseguridad.com** — blog/noticias de seguridad en español (RSS).
- **CISA KEV** — catálogo de vulnerabilidades explotadas de verdad (JSON).

Mensajes propios:

- **`consejos.json`** — un bote de consejos. Cada día se muestran unos pocos **distintos** (rotación por día del año), así el noticiero no repite siempre los mismos. Para añadir consejos, edita este archivo (una frase por línea, entre comillas).
- **`fijas.json`** — mensajes fijos puntuales (p. ej. «el tema de esta semana en clase»). Edítalo cuando cambie la clase.

La Ciberpedia lee el resultado desde:

    https://raw.githubusercontent.com/NokName/ciberpedia-noticias/main/noticias.json

## Cómo cambiar las cosas que se repiten

- **Consejos**: edita `consejos.json` (añade o quita frases). Se rotan solos.
- **Mensaje de la semana**: edita `fijas.json`.
- Al guardar cualquiera de los dos, la acción se ejecuta sola (trigger `push`) y regenera `noticias.json`.
- Para forzar una actualización a mano: pestaña **Actions** → «Actualizar noticias» → **Run workflow**.
