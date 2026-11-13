import calendar
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import actualizar_noticias as gen


class GeneradorNoticiasTests(unittest.TestCase):
    def test_json_publicado_tiene_formato_orden_y_fuentes_validas(self):
        datos = json.loads((Path(__file__).resolve().parent.parent / "noticias.json").read_text(encoding="utf-8"))
        noticias = datos["noticias"]
        self.assertTrue(1 <= len(noticias) <= gen.MAX_NOTICIAS)
        self.assertEqual([n["ts"] for n in noticias], sorted((n["ts"] for n in noticias), reverse=True))
        self.assertEqual(len({n["url"] for n in noticias}), len(noticias))
        self.assertTrue(all(n["fuente"] in gen.PRIORIDAD and n["texto"] and n["fecha"] for n in noticias))
        urgentes = [n for n in noticias if n.get("urgente")]
        self.assertLessEqual(len(urgentes), gen.MAX_URGENTES)
        self.assertTrue(all(n["fuente"] in gen.FUENTES_URGENTES for n in urgentes))

    def test_urgente_solo_lo_mas_grave_y_reciente_de_hispasec(self):
        ahora = 1792600000
        h = lambda texto, horas=1, fuente="hispasec.com": {"texto": texto, "fuente": fuente, "url": "https://e/" + texto, "ts": (ahora - horas * 3600) * 1000}
        noticias = [
            h("PHP publica parches de urgencia por dos fallos críticos"),
            h("Una campaña explota un zero-day en Citrix"),
            h("Atacantes aprovechan un fallo crítico en Atlassian"),  # solo palabra débil
            h("Ransomware en hospitales", horas=100),  # demasiado antigua
            h("CVE-2026-1 en Plex se está explotando", fuente="cisa.gov"),
            h("Un nuevo ciberataque afecta a bancos"),  # tercera: excede el máximo
        ]
        gen.marcar_urgentes(noticias, ahora)
        marcadas = [n["texto"] for n in noticias if n.get("urgente")]
        self.assertEqual(len(marcadas), 2)
        self.assertIn("Una campaña explota un zero-day en Citrix", marcadas)
        self.assertNotIn("Atacantes aprovechan un fallo crítico en Atlassian", marcadas)
        self.assertNotIn("Ransomware en hospitales", marcadas)
        self.assertNotIn("CVE-2026-1 en Plex se está explotando", marcadas)

    def test_fechas_kev_son_utc_y_el_plazo_no_se_presenta_como_futuro(self):
        feed = {"vulnerabilities": [{
            "dateAdded": "2026-10-16", "dueDate": "2026-10-19",
            "cveID": "CVE-2026-1234", "vendorProject": "Ejemplo", "product": "App",
        }]}
        with patch.object(time, "mktime", side_effect=AssertionError("No usar hora local")):
            noticia = gen.leer_kev(json.dumps(feed).encode())[0]
        esperado = calendar.timegm(time.strptime("2026-10-16", "%Y-%m-%d")) * 1000
        self.assertEqual(noticia["ts"], esperado)
        self.assertEqual(noticia["fecha"], "16 oct")
        self.assertIn("Plazo de CISA: 2026-10-19", noticia["texto"])
        self.assertNotIn("Parchea antes", noticia["texto"])

    def test_rss_sin_zona_horaria_se_interpreta_como_utc(self):
        xml = b"<rss><channel><item><title>Prueba</title><link>https://example.com/a</link><pubDate>Fri, 16 Oct 2026 10:00:00</pubDate></item></channel></rss>"
        noticia = gen.leer_rss(xml, "hispasec.com")[0]
        self.assertEqual(noticia["ts"], 1792144800000)

    def test_fallo_parcial_actualiza_fuentes_disponibles_y_conserva_la_caida(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as carpeta:
            salida = Path(carpeta) / "noticias.json"
            vieja = {"fecha": "15 oct", "texto": "Hispasec guardada", "fuente": "hispasec.com", "url": "https://example.com/h", "ts": 1792022400000}
            salida.write_text(json.dumps({"noticias": [vieja]}), encoding="utf-8")
            incibe = {"fecha": "19 oct", "texto": "INCIBE nueva", "fuente": "incibe.es", "url": "https://example.com/i", "ts": 1792368000000}
            cisa = {"fecha": "19 oct", "texto": "CISA nueva", "fuente": "cisa.gov", "url": "https://example.com/c", "ts": 1792368000000}

            def bajar(url):
                if "feedburner" in url:
                    raise OSError("fuente caída")
                return url.encode()

            fuentes = (("Hispasec", ("https://feeds.feedburner.com/hispasec/zCAd",), "hispasec.com"), ("INCIBE-CERT", ("https://example.com/incibe",), "incibe.es"))
            with patch.object(gen, "FUENTES_RSS", fuentes), patch.object(gen, "SALIDA", salida), patch.object(gen, "bajar", side_effect=bajar), patch.object(gen, "leer_rss", return_value=[incibe]), patch.object(gen, "leer_kev", return_value=[cisa]):
                gen.main()
            noticias = json.loads(salida.read_text(encoding="utf-8"))["noticias"]
            self.assertEqual({n["texto"] for n in noticias}, {"Hispasec guardada", "INCIBE nueva", "CISA nueva"})

    def test_fallo_total_no_modifica_el_archivo(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as carpeta:
            salida = Path(carpeta) / "noticias.json"
            original = '{"noticias": []}\n'
            salida.write_text(original, encoding="utf-8")
            with patch.object(gen, "SALIDA", salida), patch.object(gen, "bajar", side_effect=OSError("sin red")):
                with self.assertRaises(SystemExit):
                    gen.main()
            self.assertEqual(salida.read_text(encoding="utf-8"), original)

    def test_seleccion_reparte_entre_fuentes_y_marca_ingles(self):
        ahora = 1792600000
        mk = lambda fuente, i, dias=0, texto=None, url=None: {"fecha": "x", "texto": texto or f"{fuente} noticia {i}", "fuente": fuente, "url": url or f"https://{fuente}/{i}", "ts": (ahora - dias * 86400 - i * 60) * 1000}
        noticias = [mk("hispasec.com", i) for i in range(30)] + [mk("incibe.es", i, 1, url=f"https://www.incibe.es/incibe-cert/alerta-temprana/avisos/{i}") for i in range(10)]
        noticias += [mk("incibe.es", i, 3, url=f"https://www.incibe.es/incibe-cert/publicaciones/bitacora-de-seguridad/{i}") for i in range(5)]
        for f in ("ccn-cert.cni.es", "welivesecurity.com", "segu-info.com.ar", "bleepingcomputer.com", "thehackernews.com", "cisa.gov"):
            noticias += [mk(f, i, 2) for i in range(6)]
        noticias.append(mk("thehackernews.com", 99, 30, texto="Actualidad caducada"))
        noticias.append(mk("bleepingcomputer.com", 98, 0, texto="Fallo CVE-2026-55555 explotado"))
        noticias.append(mk("segu-info.com.ar", 97, 0, texto="Explotan CVE-2026-55555 en routers"))
        elegidas = gen.seleccionar(noticias, ahora)
        self.assertEqual(len(elegidas), gen.MAX_NOTICIAS)
        cuenta = {}
        for n in elegidas:
            cuenta[gen.clave_cupo(n)] = cuenta.get(gen.clave_cupo(n), 0) + 1
        self.assertEqual(set(cuenta), set(gen.MAX_POR_FUENTE))  # todas las fuentes presentes
        self.assertTrue(all(cuenta[c] <= gen.MAX_POR_FUENTE[c] for c in cuenta))
        textos = [n["texto"] for n in elegidas]
        self.assertNotIn("Actualidad caducada", textos)
        self.assertEqual(sum("CVE-2026-55555" in t for t in textos), 1)
        xml = b"<rss><channel><item><title>GitHub outage</title><link>https://example.com/a</link><pubDate>Fri, 16 Oct 2026 10:00:00</pubDate></item></channel></rss>"
        self.assertEqual(gen.leer_rss(xml, "bleepingcomputer.com")[0]["texto"], "[EN] GitHub outage")

    def test_fuente_usa_la_segunda_direccion_si_la_primera_falla(self):
        xml = b"<rss><channel><item><title>Aviso</title><link>https://example.com/a</link><pubDate>Fri, 16 Oct 2026 10:00:00</pubDate></item></channel></rss>"

        def bajar(url):
            if "mala" in url:
                raise OSError("404")
            return xml

        with patch.object(gen, "bajar", side_effect=bajar):
            self.assertEqual(len(gen.leer_fuente(("https://mala", "https://buena"), "ccn-cert.cni.es")), 1)


if __name__ == "__main__":
    unittest.main()
