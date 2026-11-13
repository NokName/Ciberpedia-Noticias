"""Genera noticias.json desde cero, sin intervención humana.

Fuentes de ciberseguridad:
  - Hispasec "Una al día" (RSS)
  - INCIBE-CERT, avisos de alerta temprana y bitácora de ciberseguridad (RSS)
  - CCN-CERT, avisos y alertas (RSS)
  - WeLiveSecurity en español y Segu-Info, actualidad (RSS)
  - BleepingComputer y The Hacker News, actualidad en inglés, marcada "[EN]" (RSS)
  - CISA KEV, vulnerabilidades explotadas activamente (JSON)

Qué hace en cada ejecución:
  1. Descarga todas las fuentes (si una falla, sigue con las demás).
  2. Incluye noticias, curiosidades, investigación y novedades de ciberseguridad.
     Hispasec es la fuente preferente; solo descarta contenido promocional evidente.
  3. Limpia las URLs (quita ?utm_..., fbclid, etc.) y elimina duplicados.
  4. Ordena por fecha y marca como "urgente" solo lo más grave y reciente de Hispasec
     (día cero, explotación activa, parches de urgencia, ransomware...): como mucho 2.
  5. Añade a cada noticia un "resumen" automático (2-4 frases sacadas de la propia
     fuente: entradilla del RSS o ficha de CISA), que el visor muestra en «Leer».
  6. Escribe un noticias.json NUEVO con un máximo de 18 noticias, con cupo por fuente
     para que haya avisos, vulnerabilidades y actualidad del sector.
     Nunca añade al archivo anterior y no incluye consejos (los pone el visor).
  7. Si las noticias no han cambiado, no toca el archivo (así no hay commit).

Solo usa la biblioteca estándar de Python.
"""
import calendar
import html
import json
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AQUI = pathlib.Path(__file__).parent
SALIDA = AQUI / "noticias.json"
MAX_NOTICIAS = 18
# Orden de preferencia cuando dos noticias tienen la misma fecha o cuentan lo mismo.
PRIORIDAD = {
    "hispasec.com": 0, "incibe.es": 1, "ccn-cert.cni.es": 2, "welivesecurity.com": 3,
    "segu-info.com.ar": 4, "bleepingcomputer.com": 5, "thehackernews.com": 6, "cisa.gov": 7,
}
# Cupo por fuente: ninguna puede llenar la lista ella sola. La bitácora de INCIBE
# tiene cupo propio para que los avisos técnicos no la desplacen.
MAX_POR_FUENTE = {
    "hispasec.com": 5, "incibe.es": 2, "incibe.es/bitacora": 2, "ccn-cert.cni.es": 2,
    "welivesecurity.com": 3, "segu-info.com.ar": 3, "bleepingcomputer.com": 3,
    "thehackernews.com": 3, "cisa.gov": 2,
}
# La actualidad no se queda semanas en la lista; los avisos oficiales no caducan.
DIAS_ACTUALIDAD = 10
FUENTES_ACTUALIDAD = ("welivesecurity.com", "segu-info.com.ar", "bleepingcomputer.com", "thehackernews.com")
FUENTES_EN_INGLES = ("bleepingcomputer.com", "thehackernews.com")
UA = {"User-Agent": "Mozilla/5.0 (ciberpedia-noticias; +https://github.com/NokName/Ciberpedia-Noticias)"}
UA_NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# (nombre, direcciones del feed por orden de preferencia, fuente). Se usa la primera que responda.
FUENTES_RSS = (
    ("Hispasec", ("https://feeds.feedburner.com/hispasec/zCAd",), "hispasec.com"),
    ("INCIBE-CERT", ("https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed",), "incibe.es"),
    ("INCIBE bitácora", (
        "https://www.incibe.es/incibe-cert/publicaciones/bitacora-de-seguridad/feed",
        "https://www.incibe.es/incibe-cert/alerta-temprana/bitacora-ciberseguridad/feed",
        "https://www.incibe.es/incibe-cert/publicaciones/bitacora-de-seguridad/rss",
        "https://www.incibe.es/empresas/avisos/feed",
        "https://www.incibe.es/ciudadania/avisos/feed",
    ), "incibe.es"),
    ("CCN-CERT", (
        "https://www.ccn-cert.cni.es/es/seguridad-al-dia/avisos-ccn-cert?format=feed&type=rss",
        "https://www.ccn-cert.cni.es/es/seguridad-al-dia/alertas-ccn-cert?format=feed&type=rss",
        "https://www.ccn-cert.cni.es/es/?format=feed&type=rss",
    ), "ccn-cert.cni.es"),
    ("WeLiveSecurity", (
        "https://www.welivesecurity.com/es/rss/feed/",
        "https://feeds.feedburner.com/welivesecurity-la",
    ), "welivesecurity.com"),
    ("Segu-Info", (
        "https://blog.segu-info.com.ar/feeds/posts/default?alt=rss",
        "https://feeds.feedburner.com/NoticiasSeguridadInformatica",
    ), "segu-info.com.ar"),
    ("BleepingComputer", ("https://www.bleepingcomputer.com/feed/",), "bleepingcomputer.com"),
    ("The Hacker News", ("https://feeds.feedburner.com/TheHackersNews",), "thehackernews.com"),
)
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# Las fuentes son especializadas en ciberseguridad: no exigir palabras clave.
# Solo se excluyen anuncios puramente promocionales, no noticias ni curiosidades.
PROMOCIONAL = (
    "inscripciones abiertas", "inscripcion abierta", "apuntate al webinar",
    "registrate en el webinar", "plazas disponibles", "oferta de empleo",
    "webinar", "sponsored", "deal:", "% off", "ebook", "black friday", "giveaway",
)
# "urgente" solo para lo más relevante: Hispasec, de los últimos 3 días y con palabras fuertes.
# CISA KEV e INCIBE son avisos rutinarios (todo KEV "se explota"), así que nunca se marcan.
FUENTES_URGENTES = ("hispasec.com",)
MAX_URGENTES = 2
HORAS_URGENTE = 72
URGENTE_FUERTE = (
    "zero-day", "zero day", "0-day", "0day", "dia cero", "de urgencia", "urgente", "emergencia",
    "se explota", "explotan", "explotado", "explotada", "explotacion activa", "activamente",
    "ransomware", "ciberataque", "secuestr", "filtracion masiva", "millones de",
)
URGENTE_DEBIL = ("critic", "grave", "remota", "sin parche")
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


MAX_RESUMEN = 650
# Restos típicos de los feeds que no aportan nada al resumen
RELLENO = re.compile(
    r"(la entrada .{0,200}? se public[oó] primero en .*$|the post .{0,200}? appeared first on .*$"
    r"|\[(?:…|\.\.\.)\]|(?:leer|seguir leyendo|read) m[aá]s.*$|continuar leyendo.*$)", re.I | re.S)
# Apartados de los avisos de INCIBE-CERT
APARTADOS = (("afectados", r"recursos afectados"), ("descripcion", r"descripci[oó]n"), ("solucion", r"soluci[oó]n"))


def texto_plano(fragmento):
    """HTML del feed -> texto plano, conservando los párrafos."""
    s = html.unescape(fragmento or "")
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h\d|/ul|/ol)\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = RELLENO.sub("", s)
    lineas = [re.sub(r"[ \t\u00a0]+", " ", l).strip() for l in s.split("\n")]
    # Las etiquetas quitadas dejan huecos antes de la puntuación («26.x , 24.x»)
    lineas = [re.sub(r"\s+([,.;:!?)»])", r"\1", re.sub(r"([(«¿¡])\s+", r"\1", l)) for l in lineas]
    return "\n".join(l for l in lineas if l)


def frases(texto, limite):
    """Primeras frases completas que caben en `limite` caracteres."""
    texto = re.sub(r"\s+", " ", texto).strip()
    trozos = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡0-9«\"])", texto)
    out = ""
    for t in trozos:
        if len(out) + len(t) + 1 > limite:
            break
        out = (out + " " + t).strip()
    if not out and texto:
        corte = texto[:limite].rsplit(" ", 1)[0]
        out = corte.rstrip(",;:") + "…"
    return out


def resumir_rss(cuerpo, titulo):
    """Resumen automático a partir de la entradilla/contenido del RSS."""
    plano_txt = texto_plano(cuerpo)
    if not plano_txt:
        return ""
    # Avisos de INCIBE: «Recursos afectados / Descripción / Solución»
    patron = r"(?im)^\s*(" + "|".join(p for _, p in APARTADOS) + r")\s*:?\s*$"
    partes = re.split(patron, plano_txt)
    if len(partes) >= 3:
        secciones = {}
        for i in range(1, len(partes) - 1, 2):
            for clave, p in APARTADOS:
                if re.fullmatch(p, partes[i].strip(), re.I):
                    secciones[clave] = partes[i + 1].strip()
        bloques = []
        if secciones.get("descripcion"):
            bloques.append(frases(secciones["descripcion"], 420))
        if secciones.get("afectados"):
            bloques.append("Afecta a: " + frases(secciones["afectados"], 200))
        if secciones.get("solucion"):
            bloques.append("Qué hacer: " + frases(secciones["solucion"], 220))
        bloques = [b for b in bloques if len(b) > 12]
        if bloques:
            return "\n\n".join(bloques)[:MAX_RESUMEN + 200]
    # Hispasec abre con una entradilla que el cuerpo repite después: basta con los primeros párrafos
    parrafos, acumulado = [], 0
    for par in plano_txt.split("\n"):
        parrafos.append(par)
        acumulado += len(par)
        if acumulado >= 160:
            break
    texto = re.sub(r"\s+", " ", " ".join(parrafos))
    # No repetir el titular si el feed lo incluye al principio
    if plano(texto).startswith(plano(titulo)):
        texto = texto[len(titulo):].lstrip(" .:-–—")
    resumen = frases(texto, MAX_RESUMEN)
    return resumen if len(resumen) >= 40 else ""


def resumir_kev(v):
    """Resumen en castellano de una entrada del catálogo KEV de CISA."""
    prod = f"{v.get('vendorProject', '')} {v.get('product', '')}".strip()
    partes = [f"CISA ha añadido {v['cveID']} ({prod}) a su catálogo de vulnerabilidades que se están explotando de verdad"
              + (f" el {v['dateAdded']}" if v.get("dateAdded") else "") + "."]
    if v.get("vulnerabilityName"):
        partes.append(f"Nombre del fallo: {v['vulnerabilityName'].strip()}.".replace("..", "."))
    if str(v.get("knownRansomwareCampaignUse", "")).lower() == "known":
        partes.append("Se sabe que lo usan campañas de ransomware.")
    texto = " ".join(partes)
    if v.get("shortDescription"):
        texto += "\n\nDescripción de CISA (en inglés): " + frases(v["shortDescription"], 360)
    if v.get("requiredAction"):
        accion = "Qué hacer: aplicar las correcciones o mitigaciones del fabricante"
        accion += f" (plazo para organismos federales de EE. UU.: {v['dueDate']})." if v.get("dueDate") else "."
        texto += "\n\n" + accion
    return texto


def bajar(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code != 403:
            raise
    # Algunos servidores rechazan clientes que no parecen un navegador.
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA_NAVEGADOR), timeout=30) as r:
        return r.read()


def fecha_corta(ts):
    t = time.gmtime(ts)
    return f"{t.tm_mday} {MESES[t.tm_mon - 1]}"


def noticia(titulo, url, fuente, ts, extra="", cuerpo=""):
    """Conserva noticias y curiosidades de fuentes especializadas; evita promociones."""
    titulo = limpiar_texto(titulo)
    if not titulo:
        return None
    t = plano(titulo)
    if tiene(t, PROMOCIONAL):
        return None
    if fuente in FUENTES_EN_INGLES:
        titulo = "[EN] " + titulo
    n = {"fecha": fecha_corta(ts), "texto": titulo, "fuente": fuente, "url": limpiar_url(url), "ts": int(ts * 1000)}
    resumen = resumir_rss(cuerpo, titulo) if cuerpo else ""
    if resumen:
        n["resumen"] = resumen
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
        # El contenido completo (content:encoded) da mejor resumen que la entradilla
        cuerpo = max((hijo(it, "encoded", "content"), hijo(it, "description", "summary")), key=len)
        n = noticia(hijo(it, "title"), url, fuente, ts, extra, cuerpo)
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
            "resumen": resumir_kev(v),
        }
        out.append(n)
    return out


def puntos_urgencia(n):
    t = plano(n.get("texto", ""))
    return 2 * sum(p in t for p in URGENTE_FUERTE) + sum(p in t for p in URGENTE_DEBIL)


def marcar_urgentes(noticias, ahora=None):
    """Marca como urgente, como mucho, las MAX_URGENTES noticias más graves y recientes."""
    ahora = time.time() if ahora is None else ahora
    for n in noticias:
        n.pop("urgente", None)
    candidatas = [n for n in noticias
                  if n.get("fuente") in FUENTES_URGENTES
                  and ahora * 1000 - n.get("ts", 0) <= HORAS_URGENTE * 3600 * 1000
                  and puntos_urgencia(n) >= 2]
    for n in sorted(candidatas, key=lambda n: (-puntos_urgencia(n), -n["ts"]))[:MAX_URGENTES]:
        n["urgente"] = True
    return noticias


def clave_cupo(n):
    """La bitácora y los avisos generales de INCIBE cuentan aparte de los avisos técnicos de INCIBE-CERT."""
    if n.get("fuente") == "incibe.es" and "/alerta-temprana/avisos" not in (n.get("url") or "").lower():
        return "incibe.es/bitacora"
    return n.get("fuente", "")


CVE = re.compile(r"cve-\d{4}-\d{4,}", re.I)


def seleccionar(noticias, ahora=None):
    """Reparte la lista entre las fuentes: primero lo más reciente de cada una y
    después el resto por fecha, con cupo por fuente y sin repetir la misma noticia."""
    ahora = time.time() if ahora is None else ahora
    limite = (ahora - DIAS_ACTUALIDAD * 86400) * 1000
    validas = [n for n in noticias if n["fuente"] not in FUENTES_ACTUALIDAD or n["ts"] >= limite]
    ordenadas = sorted(validas, key=lambda n: (-n["ts"], PRIORIDAD.get(n["fuente"], 9)))
    vistas, por_cupo, out = set(), {}, []

    def agregar(n):
        if len(out) >= MAX_NOTICIAS:
            return False
        cupo = clave_cupo(n)
        claves = {plano(n["texto"])} | ({n["url"].lower()} if n["url"] else set())
        # Dos fuentes que hablan del mismo CVE cuentan la misma noticia.
        claves |= {c.lower() for c in CVE.findall(n["texto"])}
        if claves & vistas or por_cupo.get(cupo, 0) >= MAX_POR_FUENTE.get(cupo, 2):
            return False
        vistas.update(claves)
        por_cupo[cupo] = por_cupo.get(cupo, 0) + 1
        out.append(n)
        return True

    # 1) Variedad: la noticia más reciente de cada fuente, por orden de preferencia.
    for cupo in sorted(MAX_POR_FUENTE, key=lambda c: PRIORIDAD.get(c.split("/")[0], 9)):
        for n in ordenadas:
            if clave_cupo(n) == cupo and agregar(n):
                break
    # 2) El resto, por fecha, hasta agotar el cupo de cada fuente o el máximo.
    for n in ordenadas:
        if n not in out:
            agregar(n)
    return marcar_urgentes(sorted(out, key=lambda n: -n["ts"]), ahora)


def diagnostico():
    """Prueba cada fuente sin escribir nada: sirve para validar los feeds en CI."""
    for nombre, urls, fuente in FUENTES_RSS:
        for url in urls:
            try:
                nuevas = leer_rss(bajar(url), fuente)
                print(f"OK    {nombre}: {len(nuevas)} entradas · {url}")
                for n in nuevas[:2]:
                    print(f"        {n['fecha']} · {n['texto'][:90]} · resumen {len(n.get('resumen', ''))}")
            except Exception as e:
                print(f"FALLO {nombre}: {e} · {url}")


def leer_fuente(urls, fuente):
    """Devuelve las noticias de la primera dirección que responda con entradas válidas."""
    error = ValueError("sin direcciones")
    for url in urls:
        try:
            nuevas = leer_rss(bajar(url), fuente)
            if nuevas:
                return nuevas
            error = ValueError("el feed no contiene noticias válidas")
        except Exception as e:
            error = e
    raise error


def main():
    try:
        anterior = json.loads(SALIDA.read_text(encoding="utf-8")).get("noticias")
        if not isinstance(anterior, list):
            anterior = []
    except Exception:
        anterior = []
    noticias, fallos, fuentes_fallidas, fuentes_ok = [], [], set(), 0
    for nombre, urls, fuente in FUENTES_RSS:
        try:
            noticias += leer_fuente(urls, fuente)
            fuentes_ok += 1
        except Exception as e:  # una fuente caída no rompe el resto
            fallos.append(f"{nombre}: {e}")
            fuentes_fallidas.add("incibe.es/bitacora" if "bitácora" in nombre else fuente)
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
    noticias += [dict(n) for n in anterior if isinstance(n, dict) and clave_cupo(n) in fuentes_fallidas]
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
    import sys
    diagnostico() if "--diagnostico" in sys.argv else main()
