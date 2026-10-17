"""Genera noticias.json: solo NOTICIAS reales, totalmente automático.

No hay nada que editar a mano. Las noticias se recogen de fuentes fiables,
con PREFERENCIA a Hispasec y a las más recientes:

  - Hispasec "una-al-día": noticias de seguridad en español (RSS)  [preferente]
  - INCIBE-CERT: avisos de alerta temprana del CERT español (RSS)
  - CISA KEV: vulnerabilidades explotadas de verdad (JSON)

Los CONSEJOS ya no viven aquí: los genera la tarea programada a partir de las
propias fichas de la Ciberpedia, así que se amplían solos según crece el libro.

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


def rss(url, fuente, max_items):
    """Lee un RSS genérico y devuelve items ya normalizados.

    El texto es solo el titular (sin prefijo): la fuente se muestra aparte,
    como enlace al final de cada noticia en el noticiero.
    """
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
            out.append({"fecha": fecha_corta(ts), "texto": titulo,
                        "fuente": fuente, "url": enlace, "ts": int(ts * 1000)})
        if len(out) >= max_items:
            break
    return out


def hispasec(max_items=6):  # fuente preferente: le damos más espacio
    return rss("https://feeds.feedburner.com/hispasec/zCAd", "hispasec.com", max_items)


def incibe(max_items=4):
    return rss("https://www.incibe.es/incibe-cert/alerta-temprana/avisos/feed", "incibe.es", max_items)


def cisa_kev(max_items=3):
    datos = json.loads(bajar("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"))
    vulns = sorted(datos.get("vulnerabilities", []), key=lambda v: v.get("dateAdded", ""), reverse=True)
    out = []
    for v in vulns[:max_items]:
        ts = time.mktime(time.strptime(v["dateAdded"], "%Y-%m-%d"))
        out.append({
            "fecha": fecha_corta(ts),
            "texto": f"{v['cveID']} en {v.get('vendorProject', '')} {v.get('product', '')} se está explotando. Parchea antes del {v.get('dueDate', '?')}.",
            "fuente": "cisa.gov",
            "url": "https://nvd.nist.gov/vuln/detail/" + v["cveID"],
            "ts": int(ts * 1000),
        })
    return out


def main():
    noticias, fallos = [], []
    # Orden = preferencia: Hispasec primero.
    for nombre, fuente in (("Hispasec", hispasec), ("INCIBE", incibe), ("CISA KEV", cisa_kev)):
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
    # Más recientes primero (= más relevantes)
    unicas.sort(key=lambda n: n.get("ts", 0), reverse=True)
    salida = {"generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "noticias": unicas[:15]}
    (AQUI / "noticias.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(salida['noticias'])} noticias escritas.", "Fallos: " + "; ".join(fallos) if fallos else "")


if __name__ == "__main__":
    main()
