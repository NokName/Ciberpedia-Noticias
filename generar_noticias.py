"""Genera noticias.json para el noticiero de la Ciberpedia.

Fuentes de noticias (dinámicas, cambian solas en cada ejecución):
  - INCIBE-CERT: avisos de alerta temprana (RSS)
  - Hispasec "una-al-día": noticias de seguridad en español (RSS)
  - ciberseguridad.com: blog/noticias de seguridad en español (RSS)
  - CISA KEV: vulnerabilidades explotadas de verdad (JSON)

Fuentes propias:
  - consejos.json: bote de consejos; cada día se muestran unos pocos DISTINTOS
    (rotación por día del año), así no se repiten siempre los mismos.
  - fijas.json: mensajes fijos puntuales (p. ej. el tema de la semana), opcional.

Solo usa la biblioteca estándar de Python. Si una fuente falla, sigue con las demás.
"""
import json
import pathlib
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

AQUI = pathlib.Path(__file__).parent
UA = {"User-Agent": "ciberpedia-noticias/1.0"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def bajar(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fecha_corta(ts):
    t = time.gmtime(ts)
    return f"{t.tm_mday} {MESES[t.tm_mon - 1]}"


def rss(url, prefijo, fuente, max_items):
    """Lee un RSS genérico y devuelve items ya normalizados."""
    raiz = ET.fromstring(bajar(url))
    out = []
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        enlace = (it.findtext("link") or "").strip()
        try:
            ts = parsedate_to_datetime(it.findtext("pubDate")).timestamp()
        except Exception:
            ts = time.time()
        if titulo:
            out.append({"fecha": fecha_corta(ts), "texto": f"{prefijo}: {titulo}",
                        "fuente": fuente, "url": enlace, "ts": int(ts * 1000)})
        if len(out) >= max_items:
            break
    return out


def incibe(max_items=4):
    return rss("https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed",
               "INCIBE-CERT", "incibe.es", max_items)


def hispasec(max_items=4):
    return rss("https://feeds.feedburner.com/hispasec/zCAd",
               "Hispasec", "hispasec.com", max_items)


def ciberseguridad(max_items=2):
    return rss("https://ciberseguridad.com/feed/",
               "ciberseguridad.com", "ciberseguridad.com", max_items)


def cisa_kev(max_items=4):
    datos = json.loads(bajar("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"))
    vulns = sorted(datos.get("vulnerabilities", []), key=lambda v: v.get("dateAdded", ""), reverse=True)
    out = []
    for v in vulns[:max_items]:
        ts = time.mktime(time.strptime(v["dateAdded"], "%Y-%m-%d"))
        out.append({
            "fecha": fecha_corta(ts),
            "texto": f"KEV: {v['cveID']} en {v.get('vendorProject', '')} {v.get('product', '')} se está explotando. Parchea antes del {v.get('dueDate', '?')}.",
            "fuente": "cisa.gov",
            "url": "https://nvd.nist.gov/vuln/detail/" + v["cveID"],
            "ts": int(ts * 1000),
        })
    return out


def consejos(cuantos=3):
    """Elige unos pocos consejos DISTINTOS cada día, rotando por el día del año.

    Así el noticiero no repite siempre los mismos consejos: el subconjunto
    cambia a diario y recorre todo el bote antes de empezar de nuevo.
    """
    f = AQUI / "consejos.json"
    if not f.exists():
        return []
    bote = json.loads(f.read_text(encoding="utf-8"))
    if not bote:
        return []
    dia = time.gmtime().tm_yday  # 1..366
    n = min(cuantos, len(bote))
    inicio = (dia * n) % len(bote)
    ahora = int(time.time() * 1000)
    out = []
    for k in range(n):
        texto = bote[(inicio + k) % len(bote)]
        # ts un poco por debajo de "ahora" para que queden intercalados, no siempre arriba
        out.append({"fecha": "Consejo", "texto": texto, "ts": ahora - (k + 1) * 3600_000})
    return out


def fijas():
    f = AQUI / "fijas.json"
    if not f.exists():
        return []
    ahora = int(time.time() * 1000)
    # Las fijas van delante: les damos la marca de tiempo más reciente
    lista = json.loads(f.read_text(encoding="utf-8"))
    return [dict(n, ts=n.get("ts", ahora + len(lista) - i)) for i, n in enumerate(lista)]


def main():
    noticias, fallos = [], []
    fuentes = (
        ("INCIBE", incibe),
        ("Hispasec", hispasec),
        ("ciberseguridad.com", ciberseguridad),
        ("CISA KEV", cisa_kev),
        ("consejos", consejos),
        ("fijas", fijas),
    )
    for nombre, fuente in fuentes:
        try:
            noticias += fuente()
        except Exception as e:  # una fuente caída no rompe el resto
            fallos.append(f"{nombre}: {e}")
    if not noticias:
        raise SystemExit("Ninguna fuente respondió; se mantiene el noticias.json anterior. " + "; ".join(fallos))
    # Quita titulares repetidos (por texto) conservando el primero
    vistas, unicas = set(), []
    for n in noticias:
        clave = n.get("texto", "")
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(n)
    unicas.sort(key=lambda n: n.get("ts", 0), reverse=True)
    salida = {"generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "noticias": unicas[:15]}
    (AQUI / "noticias.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(salida['noticias'])} noticias escritas.", "Fallos: " + "; ".join(fallos) if fallos else "")


if __name__ == "__main__":
    main()
