"""Titulos de profesores cifrados en la base (paso 9b, N6 y decisiones del 02-nov).

Se guardan cifrados (no en disco), soporte los ve como imagen con marca de agua y
el original se borra al aprobar o rechazar. Datos ficticios.
"""

import io
import tempfile
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from alumnos.models import Profesor
from apoderados.documentos import ERROR_PDF_PAGINAS, descifrar
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PasarTitulosABaseTests(TestCase):
    """manage.py pasar_titulos_a_base (9b-2): los titulos que quedaron en disco."""

    def setUp(self):
        crear_agente('10000001-9', Ticket.TITULOS)
        self.profesor = crear_profesor()

    def antiguo(self, estado, con_archivo=True):
        """Titulo como quedaba antes del paso 9b: en disco, sin cifrar."""
        self.original = bytes_pdf()
        self.profesor.titulo_archivo.save('profesor_1.pdf', ContentFile(self.original), save=False)
        self.ruta = self.profesor.titulo_archivo.path
        if not con_archivo:  # Railway borro el disco en un deploy
            self.profesor.titulo_archivo.storage.delete(self.profesor.titulo_archivo.name)
        self.profesor.titulo_estado = estado
        self.profesor.save()
        if estado == Profesor.TITULO_EN_REVISION:
            abrir_ticket(Ticket.TITULOS, profesor=self.profesor)

    def pasar(self):
        salida = StringIO()
        call_command('pasar_titulos_a_base', stdout=salida)
        self.profesor.refresh_from_db()
        return salida.getvalue()

    def test_en_revision_se_cifra_y_sigue_en_revision(self):
        self.antiguo(Profesor.TITULO_EN_REVISION)
        self.assertIn('pasados a la base: 1', self.pasar())
        self.assertEqual(descifrar(self.profesor.titulo_contenido), self.original)
        self.assertEqual(self.profesor.titulo_formato, 'PDF')
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_EN_REVISION)
        self.assertEqual(self.profesor.tickets.get().estado, Ticket.ABIERTO)
        self.assertFalse(self.profesor.titulo_archivo)
        with self.assertRaises(FileNotFoundError):
            open(self.ruta, 'rb')

    def test_si_el_archivo_se_perdio_se_pide_de_nuevo(self):
        self.antiguo(Profesor.TITULO_EN_REVISION, con_archivo=False)
        self.assertIn('debe volver a subirlo): 1', self.pasar())
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_RECHAZADO)
        self.assertEqual(self.profesor.titulo_observacion, titulo.NO_SE_RECUPERO)
        self.assertTrue(self.profesor.puede_subir_titulo)
        self.assertEqual(self.profesor.tickets.get().estado, Ticket.CERRADO)
        self.assertFalse(self.profesor.titulo_archivo)

    def test_ya_decidido_solo_se_borra(self):
        self.antiguo(Profesor.TITULO_APROBADO)
        self.assertIn('borrados del disco: 1', self.pasar())
        self.assertIsNone(self.profesor.titulo_contenido)
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_APROBADO)
        with self.assertRaises(FileNotFoundError):
            open(self.ruta, 'rb')

    def test_correrlo_otra_vez_no_hace_nada(self):
        self.antiguo(Profesor.TITULO_EN_REVISION)
        self.pasar()
        contenido = bytes(self.profesor.titulo_contenido)
        salida = self.pasar()
        self.assertIn('pasados a la base: 0', salida)
        self.assertEqual(bytes(self.profesor.titulo_contenido), contenido)
