import calendar
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import actualizar_noticias as gen


class GeneradorNoticiasTests(unittest.TestCase):
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

            with patch.object(gen, "SALIDA", salida), patch.object(gen, "bajar", side_effect=bajar), patch.object(gen, "leer_rss", return_value=[incibe]), patch.object(gen, "leer_kev", return_value=[cisa]):
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


if __name__ == "__main__":
    unittest.main()
