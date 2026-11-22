"""Iconos, letras y SweetAlert2 salen del propio sitio (static/vendor), no de internet. Datos ficticios.

Pedirlos a jsDelivr, Google Fonts o cdnjs mandaba la IP de cada visita a un tercero, dejaba el sitio sin iconos, letras ni
avisos cuando la conexion fallaba y obligaba a permitir esos dominios en la CSP. Ver lbwus/static/vendor/LEEME.txt.
"""
import os
import posixpath
import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte

BASE = Path(settings.BASE_DIR)
VENDOR = BASE / 'lbwus' / 'static' / 'vendor'
PROHIBIDO = re.compile(r'fonts\.googleapis\.com|fonts\.gstatic\.com|cdnjs\.cloudflare\.com|cdn\.jsdelivr\.net|bootstrap-icons@')
SWEETALERT = 'vendor/sweetalert2/sweetalert2.all.min.js'
PLANTILLAS_CON_AVISOS = (
    'admin_portal/templates/admin_portal/base_admin.html', 'alumnos/templates/alumnos/Alumno_pag1.html',
    'alumnos/templates/alumnos/contactos.html', 'alumnos/templates/alumnos/regis_alum.html',
    'user_profesor/templates/user_profesor/regis_prof.html', 'user_profesor/templates/user_profesor/regis_tutor.html',
)
OMITIR_CARPETAS = {'.git', 'node_modules', 'staticfiles', 'tests', 'docs', 'media', '__pycache__'}
# Un correo no puede traer archivos propios: su letra sigue pidiendose a Google Fonts.
PERMITIDOS = {BASE / 'templates' / 'registration' / 'correo_recuperacion_clave.html'}


def archivos_del_sitio():
    for carpeta, subcarpetas, archivos in os.walk(BASE):
        subcarpetas[:] = [s for s in subcarpetas if s not in OMITIR_CARPETAS and not s.startswith('.venv')]
        for archivo in archivos:
            if archivo.endswith(('.html', '.css', '.js')):
                yield Path(carpeta, archivo)


class SinRecursosExternosTests(TestCase):

    def test_ninguna_plantilla_ni_hoja_de_estilo_pide_iconos_o_letras_a_internet(self):
        pedidos = [f'{ruta.relative_to(BASE)}: {PROHIBIDO.search(texto).group()}'
                   for ruta in archivos_del_sitio() if ruta not in PERMITIDOS
                   for texto in [ruta.read_text(encoding='utf-8', errors='ignore')] if PROHIBIDO.search(texto)]
        self.assertEqual(pedidos, [])

    def test_sweetalert2_es_un_archivo_propio_con_su_licencia_y_version_fija(self):
        carpeta = VENDOR / 'sweetalert2'
        self.assertRegex((carpeta / 'sweetalert2.all.min.js').read_text(encoding='utf-8')[:80], r'sweetalert2 v11\.\d+\.\d+')
        self.assertIn('MIT License', (carpeta / 'LICENSE.txt').read_text(encoding='utf-8'))
        self.assertNotIn('sourceMappingURL', (carpeta / 'sweetalert2.all.min.js').read_text(encoding='utf-8'))  # collectstatic fallaria sin el .map
        self.assertTrue(finders.find(SWEETALERT))

    def test_las_plantillas_con_avisos_cargan_el_sweetalert2_propio(self):
        for plantilla in PLANTILLAS_CON_AVISOS:
            with self.subTest(plantilla=plantilla):
                self.assertIn(f"{{% static '{SWEETALERT}' %}}", (BASE / plantilla).read_text(encoding='utf-8'))

    def test_cada_url_de_los_css_locales_apunta_a_un_archivo_que_existe(self):
        hojas = [VENDOR / 'bootstrap-icons' / 'bootstrap-icons.min.css', VENDOR / 'fuentes' / 'fuentes.css']
        for hoja in hojas:
            direcciones = re.findall(r'url\(\s*[\'"]?([^\'")?#]+)', hoja.read_text(encoding='utf-8'))
            self.assertTrue(direcciones, hoja.name)  # si no hay ninguna, la prueba no estaria comprobando nada
            for direccion in direcciones:
                with self.subTest(hoja=hoja.name, direccion=direccion):
                    self.assertTrue((hoja.parent / direccion).is_file())

    def test_los_css_locales_cubren_las_dos_letras_y_los_iconos(self):
        letras = (VENDOR / 'fuentes' / 'fuentes.css').read_text(encoding='utf-8')
        for familia in ("font-family: 'Outfit'", "font-family: 'Inter'"):
            self.assertIn(familia, letras)
        self.assertIn('font-family:bootstrap-icons', (VENDOR / 'bootstrap-icons' / 'bootstrap-icons.min.css').read_text(
            encoding='utf-8'))

    def test_las_hojas_que_importaban_google_fonts_importan_las_letras_locales(self):
        for hoja in ('login.css', 'puerta.css', 'recuperar.css', 'admin_portal/css/admin_panel/01_base.css'):
            with self.subTest(hoja=hoja):
                texto = Path(finders.find(hoja)).read_text(encoding='utf-8')
                importada = re.search(r"@import url\('([^']*vendor/fuentes/fuentes\.css)'\)", texto)
                self.assertTrue(importada)
                # La ruta es relativa a la hoja en /static/, donde se juntan los estaticos de todas las apps.
                destino = posixpath.normpath(posixpath.join(posixpath.dirname(hoja), importada.group(1)))
                self.assertEqual(destino, 'vendor/fuentes/fuentes.css')
                self.assertTrue(finders.find(destino))


class PaginasUsanLoPropioTests(TestCase):

    def assert_usa_lo_propio(self, respuesta, letras_en_la_plantilla=True):
        self.assertContains(respuesta, 'vendor/bootstrap-icons/bootstrap-icons')
        if letras_en_la_plantilla:  # el ingreso las trae por @import desde login.css (prueba de arriba)
            self.assertContains(respuesta, 'vendor/fuentes/fuentes')
        self.assertNotRegex(respuesta.content.decode(), PROHIBIDO)

    def test_la_pagina_de_inicio_y_el_ingreso(self):
        self.assert_usa_lo_propio(self.client.get(reverse('home')))
        self.assert_usa_lo_propio(self.client.get(reverse('login')), letras_en_la_plantilla=False)

    def test_el_portal_de_soporte_que_hereda_de_la_base_de_administracion(self):
        entrar_soporte(self.client, crear_agente('10000001-9', Ticket.PAGOS))
        self.assert_usa_lo_propio(self.client.get(reverse('panel_soporte')))

    def test_la_politica_de_seguridad_ya_no_permite_dominios_externos_para_estilos_letras_ni_scripts(self):
        respuesta = self.client.get(reverse('home'))
        politica = respuesta.headers.get('Content-Security-Policy') or respuesta.headers['Content-Security-Policy-Report-Only']
        directivas = {d.split()[0]: d.split()[1:] for d in politica.split(';') if d.strip()}
        for directiva in ('style-src', 'font-src'):
            with self.subTest(directiva=directiva):
                self.assertFalse([h for h in directivas[directiva] if h.startswith('https://')], directivas[directiva])
        self.assertEqual([h for h in directivas['script-src'] if h.startswith('https://')], ['https://meet.jit.si'])  # solo Jitsi
