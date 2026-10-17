# Noticias de la Ciberpedia

Cada día, GitHub Actions ejecuta `generar_noticias.py`, que junta avisos de INCIBE-CERT, las últimas vulnerabilidades del catálogo KEV de CISA y tus mensajes de `fijas.json`, y guarda el resultado en `noticias.json`.

La Ciberpedia lee este archivo desde:

    https://raw.githubusercontent.com/TU-USUARIO/ciberpedia-noticias/main/noticias.json

Para cambiar tus mensajes (clase, consejos), edita `fijas.json`. Para forzar una actualización: pestaña Actions → "Actualizar noticias" → Run workflow.
