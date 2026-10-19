"""Genera noticias.json desde cero, sin intervención humana.

Fuentes oficiales de ciberseguridad:
  - Hispasec "Una al día" (RSS)
  - INCIBE-CERT, avisos de alerta temprana (RSS)
  - CISA KEV, vulnerabilidades explotadas activamente (JSON)

Qué hace en cada ejecución:
  1. Descarga las tres fuentes (si una falla, sigue con las demás).
  2. Incluye noticias, curiosidades, investigación y novedades de ciberseguridad.
     Hispasec es la fuente preferente; solo descarta contenido promocional evidente.
  3. Limpia las URLs (quita ?utm_..., fbclid, etc.) y elimina duplicados.
  4. Ordena por fecha; no utiliza etiquetas de urgencia.
  5. Escribe un noticias.json NUEVO con un máximo de 12 noticias.
     Nunca añade al archivo anterior y no incluye consejos (los pone el visor).
  6. Si las noticias no han cambiado, no toca el archivo (así no hay commit).

Solo usa la biblioteca estándar de Python.
"""
import calendar
import json
import pathlib
import re
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AQUI = pathlib.Path(__file__).parent
SALIDA = AQUI / "noticias.json"
MAX_NOTICIAS = 12
# Hispasec tiene preferencia real en la selección; INCIBE y CISA completan el resto
PRIORIDAD = {"hispasec.com": 0, "incibe.es": 1, "cisa.gov": 2}
MAX_POR_FUENTE = {"hispasec.com": 7, "incibe.es": 3, "cisa.gov": 2}
UA = {"User-Agent": "Mozilla/5.0 (ciberpedia-noticias; +https://github.com/NokName/Ciberpedia-Noticias)"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

FUENTES_RSS = (
    ("Hispasec", "https://feeds.feedburner.com/hispasec/zCAd", "hispasec.com"),
    ("INCIBE-CERT", "https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed", "incibe.es"),
)
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# Las fuentes son especializadas en ciberseguridad: no exigir palabras clave.
# Solo se excluyen anuncios puramente promocionales, no noticias ni curiosidades.
PROMOCIONAL = (
    "inscripciones abiertas", "inscripcion abierta", "apuntate al webinar",
    "registrate en el webinar", "plazas disponibles", "oferta de empleo",
)
PARAMS_BASURA = re.compile(r"^(utm_|fbclid$|gclid$|mc_|_hs|ref$|ref_src$|source$|feature$|igshid$|yclid$|msclkid$)", re.I)


def plano(s):
    """Minúsculas y sin tildes, para comparar palabras clave."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tiene(texto, palabras):
    return any(p in texto for p in palabras)


def limpiar_url(url):
    url = (url or "").strip()
    if not url:
        return ""
    p = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not PARAMS_BASURA.match(k)])
    return urlunsplit((p.scheme, p.netloc, p.path, query, ""))


def limpiar_texto(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def bajar(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fecha_corta(ts):
    t = time.gmtime(ts)
    return f"{t.tm_mday} {MESES[t.tm_mon - 1]}"


def noticia(titulo, url, fuente, ts, extra=""):
    """Conserva noticias y curiosidades de fuentes especializadas; evita promociones."""
    titulo = limpiar_texto(titulo)
    if not titulo:
        return None
    t = plano(titulo)
    if tiene(t, PROMOCIONAL):
        return None
    n = {"fecha": fecha_corta(ts), "texto": titulo, "fuente": fuente, "url": limpiar_url(url), "ts": int(ts * 1000)}
    return n


def hijo(el, *nombres):
    """Primer texto de un hijo, aceptando nombres con o sin espacio de nombres."""
    for c in el:
        local = c.tag.rsplit("}", 1)[-1]
        if local in nombres:
            if local == "link" and c.get("href"):
                return c.get("href")
            if c.text and c.text.strip():
                return c.text.strip()
    return ""


def leer_rss(xml, fuente):
    raiz = ET.fromstring(xml)
    out = []
    items = [e for e in raiz.iter() if e.tag.rsplit("}", 1)[-1] in ("item", "entry")]
    for it in items:
        # FeedBurner guarda el enlace original en feedburner:origLink
        url = hijo(it, "origLink") or hijo(it, "link") or hijo(it, "guid", "id")
        fecha = hijo(it, "pubDate", "published", "updated", "date")
        if not fecha:
            continue
        try:
            parsed = parsedate_to_datetime(fecha)
            ts = parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
        except Exception:
            try:
                parsed = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
                ts = parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()
            except Exception:
                continue
        extra = hijo(it, "description", "summary", "content") + " " + " ".join(
            (c.text or "") for c in it if c.tag.rsplit("}", 1)[-1] == "category")
        n = noticia(hijo(it, "title"), url, fuente, ts, extra)
        if n:
            out.append(n)
    return out


def leer_kev(raw):
    datos = json.loads(raw)
    vulns = sorted(datos.get("vulnerabilities", []), key=lambda v: v.get("dateAdded", ""), reverse=True)
    out = []
    for v in vulns[:10]:
        if not v.get("dateAdded") or not v.get("cveID"):
            continue
        ts = calendar.timegm(time.strptime(v["dateAdded"], "%Y-%m-%d"))
        prod = f"{v.get('vendorProject', '')} {v.get('product', '')}".strip()
        plazo = f" Plazo de CISA: {v['dueDate']}." if v.get("dueDate") else ""
        n = {
            "fecha": fecha_corta(ts),
            "texto": f"{v['cveID']} en {prod} se está explotando.{plazo}",
            "fuente": "cisa.gov",
            "url": "https://nvd.nist.gov/vuln/detail/" + v["cveID"],
            "ts": int(ts * 1000),
        }
        out.append(n)
    return out


def seleccionar(noticias):
    """Prioriza hasta 7 de Hispasec, completa con INCIBE/CISA y evita duplicados."""
    ordenadas = sorted(noticias, key=lambda n: (-n["ts"], PRIORIDAD.get(n["fuente"], 9)))
    vistas, por_fuente, out = set(), {}, []

    def agregar(n):
        claves = {plano(n["texto"])} | ({n["url"].lower()} if n["url"] else set())
        if claves & vistas or por_fuente.get(n["fuente"], 0) >= MAX_POR_FUENTE.get(n["fuente"], 4):
            return
        vistas.update(claves)
        por_fuente[n["fuente"]] = por_fuente.get(n["fuente"], 0) + 1
        out.append(n)

    # Reservar preferentemente espacio a Hispasec, incluso si las otras
    # fuentes publicaron entradas más recientes.
    for n in ordenadas:
        if n["fuente"] == "hispasec.com" and len(out) < MAX_NOTICIAS:
            agregar(n)
    for n in ordenadas:
        if n["fuente"] != "hispasec.com" and len(out) < MAX_NOTICIAS:
            agregar(n)
    return sorted(out, key=lambda n: -n["ts"])


def main():
    try:
        anterior = json.loads(SALIDA.read_text(encoding="utf-8")).get("noticias")
        if not isinstance(anterior, list):
            anterior = []
    except Exception:
        anterior = []
    noticias, fallos, fuentes_fallidas, fuentes_ok = [], [], set(), 0
    for nombre, url, fuente in FUENTES_RSS:
        try:
            nuevas = leer_rss(bajar(url), fuente)
            if not nuevas:
                raise ValueError("el feed no contiene noticias válidas")
            noticias += nuevas
            fuentes_ok += 1
        except Exception as e:  # una fuente caída no rompe el resto
            fallos.append(f"{nombre}: {e}")
            fuentes_fallidas.add(fuente)
    try:
        nuevas = leer_kev(bajar(KEV_URL))
        if not nuevas:
            raise ValueError("el catálogo no contiene vulnerabilidades válidas")
        noticias += nuevas
        fuentes_ok += 1
    except Exception as e:
        fallos.append(f"CISA KEV: {e}")
        fuentes_fallidas.add("cisa.gov")
    if fallos:
        print("Fallos:", "; ".join(fallos))
    if not fuentes_ok:
        raise SystemExit("Todas las fuentes fallaron; se mantiene el noticias.json anterior.")
    # Si falla una fuente, mantener sus últimas entradas sin bloquear las demás.
    noticias += [n for n in anterior if isinstance(n, dict) and n.get("fuente") in fuentes_fallidas]
    elegidas = seleccionar(noticias)
    if not elegidas:
        raise SystemExit("Ninguna fuente dio noticias válidas; se mantiene el noticias.json anterior.")
    if fallos:
        print("Actualización parcial: se conservan las últimas noticias de las fuentes fallidas.")
    if anterior == elegidas:
        print("Estás al día: no hay noticias nuevas.")
        return
    salida = {"generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "noticias": elegidas}
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(elegidas)} noticias escritas, ordenadas por fecha.")


if __name__ == "__main__":
    main()
