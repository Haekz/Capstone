"""PDF en documentos de apoderados (N6, paso 9a).

El original se guarda cifrado y nunca va al navegador: soporte ve una imagen con
marca de agua. Maximo 5 MB y 3 paginas; sin contrasena. Datos ficticios.
"""

import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from apoderados.documentos import (ERROR_FORMATO, ERROR_PDF_CLAVE, ERROR_PDF_PAGINAS, con_marca_de_agua, descifrar,
                                   preparar)
from apoderados.models import Apoderado, Documento
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, datos_registro, entrar_soporte

ENCRIPTADO = b'/Encrypt << /Filter /Standard /V 1 /R 2 /O <00> /U <00> /P -4 >>'


def bytes_pdf(paginas=1):
    salida = io.BytesIO()
    hojas = [Image.new('RGB', (600, 800), 'white') for _ in range(paginas)]
    hojas[0].save(salida, 'PDF', save_all=True, append_images=hojas[1:])
    return salida.getvalue()


def pdf(paginas=1, contenido=None):
    return SimpleUploadedFile('certificado.pdf', contenido or bytes_pdf(paginas), content_type='application/pdf')


class PrepararPdfTests(SimpleTestCase):

    def test_guarda_el_original_cifrado(self):
        original = bytes_pdf(3)
        contenido, formato = preparar(pdf(contenido=original))
        self.assertEqual(formato, 'PDF')
        self.assertFalse(contenido.startswith(b'%PDF'), 'el PDF se guardo sin cifrar')
        self.assertEqual(descifrar(contenido), original)

    def test_rechaza_lo_que_no_se_puede_mostrar(self):
        casos = {
            'cuatro paginas': (pdf(4), ERROR_PDF_PAGINAS),
            'con contrasena': (pdf(contenido=bytes_pdf().replace(b'trailer\n<<', b'trailer\n<<\n' + ENCRIPTADO)),
                               ERROR_PDF_CLAVE),
            'corrupto': (pdf(contenido=b'%PDF-1.4 documento falso'), ERROR_FORMATO),
        }
        for nombre, (archivo, error) in casos.items():
            with self.subTest(nombre), self.assertRaisesMessage(ValidationError, error):
                preparar(archivo)

    def test_se_ve_como_una_imagen_con_todas_sus_paginas(self):
        contenido, _ = preparar(pdf(2))
        imagen = Image.open(io.BytesIO(con_marca_de_agua(contenido, 'LBWUS - solo revision - Agente')))
        self.assertEqual(imagen.format, 'JPEG')
        self.assertGreater(imagen.height, 2 * imagen.width, 'faltan paginas: van una bajo otra')
        self.assertLessEqual(imagen.width, 1400)


class PdfEnElPortalTests(TestCase):

    def test_el_registro_acepta_un_pdf(self):
        self.client.post(reverse('registro_apoderado'), datos_registro(carnet_frente=pdf()))
        self.assertEqual(Apoderado.objects.get().documentos.get(tipo=Documento.CARNET_FRENTE).formato, 'PDF')

    def test_el_selector_de_archivos_ofrece_pdf(self):
        self.assertContains(self.client.get(reverse('registro_apoderado')), 'application/pdf')

    def test_soporte_ve_una_imagen_y_nunca_el_pdf(self):
        agente = crear_agente('10101010-1', Ticket.APODERADOS)
        apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        abrir_ticket(Ticket.APODERADOS, apoderado=apoderado)
        contenido, formato = preparar(pdf())
        documento = Documento.objects.create(tipo=Documento.CARNET_FRENTE, apoderado=apoderado,
                                             contenido=contenido, formato=formato)
        entrar_soporte(self.client, agente)
        respuesta = self.client.get(reverse('apoderado_documento', args=[documento.pk]))
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertNotIn(b'%PDF', respuesta.content)
