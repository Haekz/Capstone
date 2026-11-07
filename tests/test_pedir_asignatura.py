"""El lider le pide al admin crear la asignatura que propuso el profesor (fase 4, commit 3, decidido 07-nov).

Solo el lider (D5: el agente no escala directo al admin). El admin ve "Crear X" en su caso escalado, la crea y
soporte recibe la respuesta solo. Datos ficticios.
"""

from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase, Especialidad, Especializacion, Profesor
from soporte.models import Escalamiento, Ticket
from soporte.tickets import abrir_reporte, escalar
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_especialidad import crear_profesor
from tests.test_especializaciones_subida import certificado
from tests.test_retiros import crear_admin, entrar_admin
from tests.test_soporte_reportes import crear_alumno_adulto
from user_profesor import especializaciones


class PedirAsignaturaTests(TestCase):

    def preparar(self, lider, otra='Física'):
        """Un profesor con una especializacion en revision, atendida por un lider o por un agente."""
        self.agente = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES, lider=lider)
        profesor = crear_profesor('22222222-2', 'p@lbwus.cl', Especialidad.objects.create(nombre='Mate'),
                                  titulo_estado=Profesor.TITULO_PENDIENTE)
        algebra = Asignatura.objects.create(nombre='Álgebra')
        self.especializacion = especializaciones.subir(profesor, 'Diplomado en Física', certificado(),
                                                       [algebra.pk] if not otra else [], otra)
        self.ticket = profesor.tickets.get()
        self.pedir_url = reverse('pedir_asignatura', args=[self.especializacion.pk])
        entrar_soporte(self.client, self.agente)

    def pedir(self):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.pedir_url, follow=True)

    def como_admin(self):
        self.client.logout()
        entrar_admin(self.client, *crear_admin())

    def test_el_lider_la_pide_y_el_ticket_sigue_suyo(self):
        self.preparar(lider=True)
        self.assertContains(self.pedir(), 'Le pediste al administrador crear «Física»')
        escalamiento = Escalamiento.objects.get()
        self.assertEqual((escalamiento.destino, escalamiento.asignatura_pedida, escalamiento.autor),
                         (Escalamiento.AL_ADMIN, 'Física', self.agente.user))
        self.assertIn('«Física»', escalamiento.motivo)
        self.assertIn('Diplomado en Física', escalamiento.motivo)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.asignado, self.agente)  # no se reasigna

    def test_el_boton_es_solo_del_lider_y_solo_si_propone_otra(self):
        self.preparar(lider=True)
        self.assertContains(self.client.get(reverse('titulos_adm')), f'action="{self.pedir_url}"')
        Especializacion.objects.update(otra_asignatura='')
        self.assertNotContains(self.client.get(reverse('titulos_adm')), self.pedir_url)

    def test_un_agente_no_puede_pedirla_ni_ve_el_boton(self):
        self.preparar(lider=False)
        self.assertNotContains(self.client.get(reverse('titulos_adm')), self.pedir_url)
        self.client.post(self.pedir_url)
        self.assertFalse(Escalamiento.objects.exists())
        with self.assertRaisesMessage(Exception, 'Solo el líder de soporte'):
            escalar(self.ticket, self.agente, 'motivo', asignatura_pedida='Física')

    def test_sin_otra_no_hay_pedido(self):
        self.preparar(lider=True, otra='')
        self.assertContains(self.pedir(), 'no propone una asignatura nueva')
        self.assertFalse(Escalamiento.objects.exists())

    def test_un_pedido_pendiente_no_se_repite(self):
        self.preparar(lider=True)
        self.pedir()
        self.assertContains(self.pedir(), 'ya está escalado')
        self.assertEqual(Escalamiento.objects.count(), 1)

    def test_otro_profesor_no_puede_pedirla_con_un_id_ajeno(self):
        self.preparar(lider=True)
        otro = crear_agente('10000009-8', Ticket.ESPECIALIZACIONES, lider=True)
        entrar_soporte(self.client, otro)  # no tiene el ticket de esa especializacion
        self.assertEqual(self.client.post(self.pedir_url).status_code, 404)
        self.assertFalse(Escalamiento.objects.exists())

    def test_el_admin_la_crea_soporte_recibe_la_respuesta_y_aprueba_con_ella(self):
        self.preparar(lider=True)
        self.pedir()
        self.como_admin()
        pagina = self.client.get(reverse('casos_escalados'))
        escalamiento = Escalamiento.objects.get()
        self.assertContains(pagina, 'Crear «Física» y avisar a soporte')
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk]), follow=True)
        self.assertContains(respuesta, 'Creé la asignatura «Física»')
        fisica = Asignatura.objects.get(nombre='Física')
        escalamiento.refresh_from_db()
        self.assertFalse(escalamiento.pendiente)
        self.assertIn('Creé la asignatura «Física»', escalamiento.indicacion)
        # Soporte la ve respondida y ya puede asignarla al aprobar.
        entrar_soporte(self.client, self.agente)
        self.assertContains(self.client.get(reverse('soporte_escalar', args=[self.ticket.pk])),
                            'Creé la asignatura «Física»')
        self.assertContains(self.client.get(reverse('titulos_adm')), f'value="{fisica.pk}"')
        especializaciones.resolver(self.especializacion, True, ids_asignaturas=[fisica.pk])
        self.assertTrue(Clase.objects.filter(asignatura=fisica).exists())

    def test_si_ya_existe_no_se_duplica(self):
        self.preparar(lider=True)
        self.pedir()
        existente = Asignatura.objects.create(nombre='FÍSICA')  # la creo alguien mientras tanto
        self.como_admin()
        escalamiento = Escalamiento.objects.get()
        respuesta = self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk]), follow=True)
        self.assertContains(respuesta, 'ya está en el catálogo')
        self.assertEqual(list(Asignatura.objects.filter(nombre__iexact='física')), [existente])
        escalamiento.refresh_from_db()
        self.assertFalse(escalamiento.pendiente)

    def test_no_se_crea_dos_veces_ni_en_un_caso_ordinario(self):
        self.preparar(lider=True)
        self.pedir()
        escalamiento = Escalamiento.objects.get()
        otro_ticket = abrir_reporte(crear_alumno_adulto().user, Ticket.PAGOS, 'Cobro doble', 'Detalle.')
        ordinario = Escalamiento.objects.create(ticket=otro_ticket, destino=Escalamiento.AL_ADMIN, motivo='Caso grave.')
        self.como_admin()
        self.assertEqual(self.client.post(reverse('crear_asignatura_pedida', args=[ordinario.pk])).status_code, 404)
        self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk]))
        self.assertEqual(self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk])).status_code, 404)
        self.assertEqual(Asignatura.objects.filter(nombre='Física').count(), 1)
        # El caso ordinario no ofrece "Crear".
        self.assertNotContains(self.client.get(reverse('casos_escalados')), reverse('crear_asignatura_pedida',
                                                                                     args=[ordinario.pk]))

    def test_si_otro_admin_responde_primero_no_queda_la_asignatura_creada(self):
        self.preparar(lider=True)
        self.pedir()
        escalamiento = Escalamiento.objects.get()
        self.como_admin()
        with mock.patch('admin_portal.escalados.indicar', side_effect=ValidationError('Ese caso ya tiene una indicación.')):
            respuesta = self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk]), follow=True)
        self.assertContains(respuesta, 'Ese caso ya tiene una indicación.')
        self.assertFalse(Asignatura.objects.filter(nombre='Física').exists())  # todo o nada

    def test_solo_el_admin_crea(self):
        self.preparar(lider=True)
        self.pedir()
        escalamiento = Escalamiento.objects.get()
        self.client.post(reverse('crear_asignatura_pedida', args=[escalamiento.pk]))  # sigue como lider
        self.assertFalse(Asignatura.objects.filter(nombre='Física').exists())
        escalamiento.refresh_from_db()
        self.assertTrue(escalamiento.pendiente)
