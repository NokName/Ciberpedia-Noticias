# Noticias de la Ciberpedia

La actualización se ejecuta automáticamente mientras GitHub Actions esté activo.

## Cómo funciona

Cada 6 horas, GitHub Actions (`.github/workflows/actualizar.yml`) ejecuta `actualizar_noticias.py`, que:

- Lee las fuentes oficiales: **Hispasec «Una al día»**, **INCIBE-CERT** (avisos de alerta temprana) y el catálogo **CISA KEV**.
- Conserva las noticias, investigaciones y curiosidades de las fuentes especializadas; solo descarta anuncios claramente promocionales.
- Limpia las URLs (`?utm_...`), quita duplicados y ordena por fecha (más recientes primero). No utiliza la etiqueta `urgente`. Hispasec tiene un cupo preferente de hasta 7 noticias; INCIBE y CISA aportan diversidad.
- Genera `noticias.json` **desde cero** con un máximo de 12 noticias (nunca acumula) y sin consejos: los consejos los saca el propio visor de las fichas de la Ciberpedia, uno distinto cada día.
- Solo hace commit si las noticias han cambiado de verdad. Si no cambian, el registro de Actions indica «Estás al día». Este mensaje todavía no aparece dentro de la APK: requiere una modificación posterior del visor canónico.
- Si una fuente falla, conserva sus últimas entradas y actualiza las demás. Si fallan todas, no modifica el JSON y el workflow termina con error.
- El horario es a los minutos 17 de las 00:00, 06:00, 12:00 y 18:00 UTC. GitHub puede retrasar alguna ejecución programada; el historial de Actions permite comprobarlo. GitHub desactiva workflows programados en repositorios públicos tras 60 días sin actividad.

La Ciberpedia lee el resultado (sin configurar nada) desde:

    https://raw.githubusercontent.com/NokName/Ciberpedia-Noticias/main/noticias.json

## Forzar una actualización a mano

Pestaña **Actions** → «Actualizar noticias» → **Run workflow**.

## App Android (carpeta `app/`)

- `app/Ciberpedia.apk`: la app de la Ciberpedia para Android.
- `app/version.json`: la versión publicada. La app lo consulta al abrirse y avisa si hay una nueva.
- El workflow de noticias no toca esta carpeta.
