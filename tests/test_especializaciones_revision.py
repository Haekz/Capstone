"""Soporte revisa las especializaciones una por una (fase 2, commit 3, 06-nov).

Solo el agente con el ticket de especializaciones del profesor ve el certificado (con marca de agua y
registro de acceso) y decide. Al decidir se borra el documento; el ticket se cierra cuando no queda
ninguna pendiente. El ticket del titulo no da acceso ni se toca. Datos ficticios.
"""

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from admin_portal.models import AccesoTitulo
from alumnos.models import Asignatura, Especializacion
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_apoderados_pdf import bytes_pdf
from tests.test_soporte import crear_profesor
from user_profesor import especializaciones, titulo


def pdf(nombre):
    return SimpleUploadedFile(nombre, bytes_pdf())


class RevisionEspecializacionesTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        self.agente_titulos = crear_agente('10000001-9', Ticket.TITULOS)
        self.profesor = crear_profesor()
        titulo.subir(self.profesor, pdf('titulo.pdf'))  # su ticket de titulo no debe tocarse
        algebra = Asignatura.objects.create(nombre='Álgebra')
        self.a = especializaciones.subir(self.profesor, 'Diplomado A', pdf('a.pdf'), [algebra.pk])
        self.b = especializaciones.subir(self.profesor, 'Magíster B', pdf('b.pdf'), [algebra.pk])

    def ticket(self, categoria):
        return self.profesor.tickets.get(categoria=categoria)

    def decidir(self, especializacion, decision, observacion=''):
        return self.client.post(reverse('resolver_especializacion', args=[especializacion.pk]),
                                {'decision': decision, 'observacion': observacion})

    def test_el_agente_de_especializaciones_las_ve_y_abre_el_certificado_con_registro(self):
        entrar_soporte(self.client, self.agente)
        pagina = self.client.get(reverse('titulos_adm'))
        self.assertContains(pagina, 'Especializaciones pendientes de revisión (2)')
        self.assertContains(pagina, 'Diplomado A')
        self.assertContains(pagina, 'Álgebra')
        respuesta = self.client.get(reverse('ver_especializacion', args=[self.a.pk]))
        self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'image/jpeg'))
        self.assertIn('no-store', respuesta['Cache-Control'])
        acceso = AccesoTitulo.objects.get()
        self.assertEqual((acceso.agente, acceso.especializacion), (self.agente.user, self.a))

    def test_el_agente_del_titulo_no_las_ve_ni_las_abre_ni_las_decide(self):
        entrar_soporte(self.client, self.agente_titulos)
        self.assertNotContains(self.client.get(reverse('titulos_adm')), 'Diplomado A')
        self.assertEqual(self.client.get(reverse('ver_especializacion', args=[self.a.pk])).status_code, 404)
        self.assertEqual(self.decidir(self.a, 'aprobar').status_code, 404)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, Especializacion.EN_REVISION)
        self.assertFalse(AccesoTitulo.objects.exists())

    def test_cada_una_se_decide_aparte_y_el_ticket_se_cierra_con_la_ultima(self):
        entrar_soporte(self.client, self.agente)
        self.decidir(self.a, 'aprobar')
        self.a.refresh_from_db()
        self.assertEqual((self.a.estado, self.a.contenido, self.a.formato), (Especializacion.APROBADA, None, ''))
        self.assertIsNotNone(self.a.revisada)
        self.assertEqual(self.ticket(Ticket.ESPECIALIZACIONES).estado, Ticket.ABIERTO)  # queda B

        self.decidir(self.b, 'rechazar', 'El certificado no muestra la institución')
        self.b.refresh_from_db()
        self.assertEqual((self.b.estado, self.b.observacion, self.b.contenido),
                         (Especializacion.RECHAZADA, 'El certificado no muestra la institución', None))
        self.assertEqual(self.ticket(Ticket.ESPECIALIZACIONES).estado, Ticket.CERRADO)
        self.assertEqual(self.ticket(Ticket.TITULOS).estado, Ticket.ABIERTO)  # el titulo sigue su curso

    def test_rechazar_sin_motivo_no_decide(self):
        entrar_soporte(self.client, self.agente)
        respuesta = self.client.post(reverse('resolver_especializacion', args=[self.a.pk]),
                                     {'decision': 'rechazar', 'observacion': '   '}, follow=True)
        self.assertContains(respuesta, 'Indica el motivo del rechazo.')
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, Especializacion.EN_REVISION)
        self.assertIsNotNone(self.a.contenido)

    def test_no_se_decide_dos_veces(self):
        especializaciones.resolver(self.a, aprobar=True)
        with self.assertRaisesMessage(ValidationError, 'no está pendiente'):
            especializaciones.resolver(self.a, aprobar=False, observacion='tarde')
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, Especializacion.APROBADA)

    def test_revisar_en_el_panel_de_soporte_lleva_a_documentos_de_profesores(self):
        entrar_soporte(self.client, self.agente)
        html = self.client.get(reverse('panel_soporte')).content.decode()
        self.assertIn(f'href="{reverse("titulos_adm")}">Revisar', html)
        self.assertNotIn(f'href="{reverse("apoderados_revision")}">Revisar', html)

    def test_el_lider_ve_que_documento_se_abrio(self):
        lider = crear_agente('10000003-5', lider=True)
        AccesoTitulo.objects.create(agente=self.agente_titulos.user, profesor=self.profesor)
        AccesoTitulo.objects.create(agente=self.agente.user, profesor=self.profesor, especializacion=self.a)
        entrar_soporte(self.client, lider)
        pagina = self.client.get(reverse('titulos_adm'))
        self.assertContains(pagina, 'Especialización: Diplomado A')
        self.assertContains(pagina, '<td>Título</td>', html=True)
