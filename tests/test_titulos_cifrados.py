"""Titulos de profesores cifrados en la base (paso 9b, N6 y decisiones del 02-nov).

Se guardan cifrados (no en disco), soporte los ve como imagen con marca de agua y
el original se borra al aprobar o rechazar. Datos ficticios.
"""

import io
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from alumnos.models import Profesor
from apoderados.documentos import ERROR_PDF_PAGINAS, descifrar
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte, imagen
from tests.test_apoderados_pdf import bytes_pdf
from tests.test_soporte import crear_profesor
from user_profesor import titulo


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TitulosCifradosTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.TITULOS)
        self.profesor = crear_profesor()
        self.url = reverse('ver_titulo', args=[self.profesor.pk])

    def subir(self, archivo=None):
        titulo.subir(self.profesor, archivo or SimpleUploadedFile('titulo.pdf', bytes_pdf(2)))
        self.profesor.refresh_from_db()

    def test_soporte_ve_una_imagen_con_marca_de_agua_y_nunca_el_original(self):
        self.subir()
        entrar_soporte(self.client, self.agente)
        respuesta = self.client.get(self.url)
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertEqual(respuesta['Content-Disposition'], 'inline')
        self.assertIn('no-store', respuesta['Cache-Control'])
        self.assertNotIn(b'%PDF', respuesta.content)

    def test_una_foto_se_guarda_re_codificada(self):
        self.subir(imagen('titulo.png', 'PNG'))
        self.assertEqual(self.profesor.titulo_formato, 'PNG')
        self.assertEqual(Image.open(io.BytesIO(descifrar(self.profesor.titulo_contenido))).format, 'PNG')

    def test_un_pdf_de_mas_de_3_paginas_no_se_acepta(self):
        with self.assertRaisesMessage(ValidationError, ERROR_PDF_PAGINAS):
            self.subir(SimpleUploadedFile('titulo.pdf', bytes_pdf(4)))
        self.assertEqual(Profesor.objects.get(pk=self.profesor.pk).titulo_estado, Profesor.TITULO_PENDIENTE)

    def test_al_decidir_se_borra_el_original(self):
        for aprobar, observacion in ((True, ''), (False, 'Ilegible')):
            with self.subTest(aprobar=aprobar):
                Profesor.objects.filter(pk=self.profesor.pk).update(titulo_estado=Profesor.TITULO_PENDIENTE)
                self.profesor.refresh_from_db()
                self.subir()
                titulo.resolver(self.profesor, aprobar, observacion)
                self.profesor.refresh_from_db()
                self.assertIsNone(self.profesor.titulo_contenido)
                self.assertEqual(self.profesor.titulo_formato, '')
                entrar_soporte(self.client, self.agente)
                self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_subir_uno_nuevo_borra_el_archivo_antiguo_del_disco(self):
        self.profesor.titulo_archivo.save('profesor_antiguo.pdf', ContentFile(bytes_pdf()), save=True)
        ruta = self.profesor.titulo_archivo.path
        self.subir()
        self.assertFalse(self.profesor.titulo_archivo)
        with self.assertRaises(FileNotFoundError):
            open(ruta, 'rb')
