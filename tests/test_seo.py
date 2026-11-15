"""Lo basico para buscadores y vistas previas: descripcion, direccion canonica, Open Graph, robots.txt y sitemap.xml."""
import re
import xml.etree.ElementTree as ET

from django.test import TestCase, override_settings
from django.urls import reverse

from lbwus.seo import RUTAS_PRIVADAS

SITIO = 'https://lbwus.xyz'
# A mano, no importada del codigo: si alguien quita una pagina del sitemap, esta prueba debe notarlo.
PAGINAS_PUBLICAS = ('home', 'nosotros', 'servicios', 'planes', 'contactos')


def etiqueta(respuesta, patron):
    encontrada = re.search(patron, respuesta.content.decode())
    return encontrada.group(1) if encontrada else None


class DescripcionYVistaPreviaTests(TestCase):

    def test_cada_pagina_publica_tiene_su_propia_descripcion_de_largo_razonable(self):
        descripciones = {}
        for nombre in PAGINAS_PUBLICAS:
            descripciones[nombre] = etiqueta(self.client.get(reverse(nombre)), r'<meta name="description" content="([^"]*)">')
            with self.subTest(pagina=nombre):
                self.assertTrue(descripciones[nombre])
                self.assertTrue(40 <= len(descripciones[nombre]) <= 160, len(descripciones[nombre]))  # Google corta en ~160
        self.assertEqual(len(set(descripciones.values())), len(PAGINAS_PUBLICAS))  # ninguna repetida

    def test_la_direccion_canonica_usa_el_sitio_sin_parametros_ni_el_dominio_de_entrada(self):
        ruta = reverse('nosotros')
        respuesta = self.client.get(ruta + '?utm_source=correo', HTTP_HOST='capstone-production-eddd.up.railway.app')
        self.assertEqual(etiqueta(respuesta, r'<link rel="canonical" href="([^"]*)">'), SITIO + ruta)
        self.assertEqual(etiqueta(respuesta, r'<meta property="og:url" content="([^"]*)">'), SITIO + ruta)

    @override_settings(SITIO_URL='https://otro.test')
    def test_la_direccion_sale_del_ajuste_SITIO_URL(self):
        respuesta = self.client.get(reverse('home'))
        self.assertEqual(etiqueta(respuesta, r'<link rel="canonical" href="([^"]*)">'), 'https://otro.test/')
        self.assertContains(respuesta, 'content="https://otro.test/static/alumnos/img/Logo')

    def test_open_graph_y_tarjeta_para_whatsapp_y_redes(self):
        respuesta = self.client.get(reverse('home'))
        for propiedad, valor in (('og:type', 'website'), ('og:site_name', 'LBWUS'), ('og:locale', 'es_CL')):
            with self.subTest(propiedad=propiedad):
                self.assertEqual(etiqueta(respuesta, rf'<meta property="{propiedad}" content="([^"]*)">'), valor)
        imagen = etiqueta(respuesta, r'<meta property="og:image" content="([^"]*)">')
        self.assertTrue(imagen.startswith(SITIO + '/static/') and 'Logo' in imagen, imagen)  # absoluta, no relativa
        self.assertEqual(etiqueta(respuesta, r'<meta name="twitter:card" content="([^"]*)">'), 'summary')


class RobotsTests(TestCase):

    def test_pide_no_rastrear_las_zonas_privadas_y_apunta_al_sitemap(self):
        respuesta = self.client.get('/robots.txt')
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'text/plain; charset=utf-8'))
        texto = respuesta.content.decode()
        self.assertIn('User-agent: *\n', texto)
        for ruta in RUTAS_PRIVADAS:
            with self.subTest(ruta=ruta):
                self.assertIn(f'Disallow: {ruta}\n', texto)
        self.assertTrue(texto.endswith(f'Sitemap: {SITIO}/sitemap.xml\n'))

    def test_no_bloquea_ninguna_pagina_publica(self):
        texto = self.client.get('/robots.txt').content.decode()
        self.assertIsNone(re.search(r'^Disallow:\s*/?\s*$', texto, re.MULTILINE))  # ni «Disallow: /» ni uno vacio
        for nombre in PAGINAS_PUBLICAS:
            with self.subTest(pagina=nombre):
                self.assertFalse(reverse(nombre).startswith(RUTAS_PRIVADAS))

    def test_solo_se_puede_consultar(self):
        self.assertEqual(self.client.post('/robots.txt').status_code, 405)


class SitemapTests(TestCase):

    def direcciones(self):
        respuesta = self.client.get('/sitemap.xml')
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'application/xml; charset=utf-8'))
        espacio = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        return [loc.text for loc in ET.fromstring(respuesta.content).findall('s:url/s:loc', espacio)]

    def test_lista_las_paginas_publicas_con_direccion_completa(self):
        self.assertEqual(self.direcciones(), [SITIO + reverse(nombre) for nombre in PAGINAS_PUBLICAS])

    def test_todas_responden_sin_iniciar_sesion_y_ninguna_es_privada(self):
        for direccion in self.direcciones():
            ruta = direccion.removeprefix(SITIO)
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(ruta).status_code, 200)  # un sitemap con enlaces rotos es peor que ninguno
                self.assertFalse(ruta.startswith(RUTAS_PRIVADAS))

    @override_settings(SITIO_URL='https://otro.test')
    def test_usa_el_ajuste_SITIO_URL(self):
        self.assertTrue(all(d.startswith('https://otro.test/') for d in self.direcciones()))
