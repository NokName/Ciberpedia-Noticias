import unittest

import actualizar_noticias as gen

HISPASEC = """<?xml version="1.0"?><rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:feedburner="http://rssnamespace.org/feedburner/ext/1.0"><channel>
<item><title>Node.js corrige un fallo grave en Brotli</title><link>https://feedproxy/x</link>
<feedburner:origLink>https://unaaldia.hispasec.com/2026/11/node.html?utm_source=rss</feedburner:origLink>
<pubDate>Tue, 10 Nov 2026 08:00:00 +0000</pubDate>
<description><![CDATA[<p>Node.js corrige un fallo grave en Brotli [&#8230;]</p>]]></description>
<content:encoded><![CDATA[<p>Node.js ha publicado versiones que corrigen una escritura fuera de l&iacute;mites en el decodificador Brotli.</p><p>El fallo aparece al descomprimir contenido manipulado. Las versiones 22.23.4 y 24.22.1 ya lo corrigen. Conviene actualizar cuanto antes.</p><p>La entrada <a href="#">Node.js corrige</a> se public&oacute; primero en Una al d&iacute;a.</p>]]></content:encoded>
</item></channel></rss>"""

INCIBE = """<?xml version="1.0"?><rss><channel><item><title>Escalada de privilegios en Iperius Backup</title>
<link>https://www.incibe.es/incibe-cert/alerta-temprana/avisos/escalada</link><pubDate>Wed, 11 Nov 2026 07:00:00 +0100</pubDate>
<description><![CDATA[<h3>Recursos afectados</h3><ul><li>Iperius Backup, versiones anteriores a 8.6.</li></ul><h3>Descripción</h3><p>Se ha detectado una vulnerabilidad que permite a un usuario local escalar privilegios. Un atacante podría ejecutar código como SYSTEM.</p><h3>Solución</h3><p>Actualizar a la versión 8.6 o posterior.</p>]]></description>
</item></channel></rss>"""


class ResumenesTests(unittest.TestCase):
    def test_hispasec_resume_el_contenido_sin_relleno(self):
        n = gen.leer_rss(HISPASEC.encode(), "hispasec.com")[0]
        r = n["resumen"]
        self.assertIn("escritura fuera de límites", r)
        self.assertNotIn("se publicó primero", r)
        self.assertNotIn("<", r)
        self.assertLessEqual(len(r), gen.MAX_RESUMEN)
        self.assertEqual(n["url"], "https://unaaldia.hispasec.com/2026/11/node.html")

    def test_incibe_usa_descripcion_afectados_y_solucion(self):
        r = gen.leer_rss(INCIBE.encode(), "incibe.es")[0]["resumen"]
        self.assertTrue(r.startswith("Se ha detectado una vulnerabilidad"))
        self.assertIn("Afecta a: Iperius Backup", r)
        self.assertIn("Qué hacer: Actualizar a la versión 8.6", r)

    def test_kev_resumen_en_castellano(self):
        v = {"cveID": "CVE-2026-1", "vendorProject": "Acme", "product": "VPN", "dateAdded": "2026-11-10",
             "vulnerabilityName": "Acme VPN Authentication Bypass", "shortDescription": "Acme VPN contains an authentication bypass.",
             "requiredAction": "Apply mitigations.", "dueDate": "2026-12-01", "knownRansomwareCampaignUse": "Known"}
        r = gen.resumir_kev(v)
        self.assertIn("CISA ha añadido CVE-2026-1 (Acme VPN)", r)
        self.assertIn("ransomware", r)
        self.assertIn("2026-12-01", r)

    def test_sin_cuerpo_no_hay_resumen(self):
        n = gen.noticia("Titular", "https://e/x", "hispasec.com", 1792600000)
        self.assertNotIn("resumen", n)

    def test_sin_huecos_antes_de_puntuacion_ni_cuerpo_repetido(self):
        cuerpo = ("<p><strong>Node.js publicó versiones para 26.x</strong> , <strong>24.x</strong> y <strong>22.x</strong> . "
                  "El lote corrige fallos de TLS y Brotli y actualiza OpenSSL, Undici y otras dependencias del proyecto en todas sus ramas.</p>"
                  "<p>Los equipos que despliegan Node.js tienen una actualización urgente: el proyecto publicó versiones para 26.x, 24.x y 22.x.</p>")
        r = gen.resumir_rss(cuerpo, "Node.js corrige fallos")
        self.assertIn("26.x, 24.x y 22.x.", r)
        self.assertNotIn(" ,", r)
        self.assertNotIn("Los equipos", r)

    def test_frases_corta_en_frase_completa(self):
        self.assertEqual(gen.frases("Uno dos. Tres cuatro. Cinco seis.", 22), "Uno dos. Tres cuatro.")


if __name__ == "__main__":
    unittest.main()
