# Noticias de la Ciberpedia

Todo es automático: no hay que editar nada.

## Cómo funciona

**1. Noticias (este repo).** Cada 5 horas, GitHub Actions ejecuta `generar_noticias.py`, que recoge noticias reales de seguridad y las guarda en `noticias.json`, con **preferencia a Hispasec** y a las más recientes:

- **Hispasec «una-al-día»** — noticias de seguridad en español (fuente preferente).
- **INCIBE-CERT** — avisos de alerta temprana del CERT español.
- **CISA KEV** — vulnerabilidades explotadas de verdad.

La Ciberpedia lee el resultado desde:

    https://raw.githubusercontent.com/NokName/ciberpedia-noticias/main/noticias.json

**2. Consejos (automáticos, desde la propia Ciberpedia).** Una tarea programada (cada 5 horas) lee las fichas de la Ciberpedia, saca consejos de sus resúmenes rotándolos, los junta con las noticias y lo escribe todo en el noticiero del artefacto. Según crece el libro, los consejos se amplían solos. No hay archivo que mantener.

## Forzar una actualización a mano

Pestaña **Actions** → «Actualizar noticias» → **Run workflow**.
