# Noticias de la Ciberpedia

Todo es automático: no hay que editar nada.

## Cómo funciona

Cada 6 horas, GitHub Actions (`.github/workflows/actualizar.yml`) ejecuta `actualizar_noticias.py`, que:

- Lee las fuentes oficiales: **Hispasec «Una al día»**, **INCIBE-CERT** (avisos de alerta temprana) y el catálogo **CISA KEV**.
- Se queda solo con noticias de ciberseguridad y pentesting relevantes (vulnerabilidades, RCE, SQLi, Linux/Windows/Active Directory/Docker, explotación activa) y descarta el relleno.
- Limpia las URLs (`?utm_...`), quita duplicados y ordena por fecha (más recientes primero). No utiliza la etiqueta `urgente`. Hispasec tiene un cupo preferente de hasta 8 noticias; INCIBE y CISA aportan diversidad.
- Genera `noticias.json` **desde cero** con un máximo de 12 noticias (nunca acumula) y sin consejos: los consejos los saca el propio visor de las fichas de la Ciberpedia, uno distinto cada día.
- Solo hace commit si las noticias han cambiado de verdad. Si no cambian, el registro de Actions indica «Estás al día». Este mensaje todavía no aparece dentro de la APK: requiere una modificación posterior del visor canónico.

La Ciberpedia lee el resultado (sin configurar nada) desde:

    https://raw.githubusercontent.com/NokName/Ciberpedia-Noticias/main/noticias.json

## Forzar una actualización a mano

Pestaña **Actions** → «Actualizar noticias» → **Run workflow**.

## App Android (carpeta `app/`)

- `app/Ciberpedia.apk`: la app de la Ciberpedia para Android.
- `app/version.json`: la versión publicada. La app lo consulta al abrirse y avisa si hay una nueva.
- El workflow de noticias no toca esta carpeta.
