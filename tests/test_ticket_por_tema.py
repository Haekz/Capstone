"""Tickets de revision del profesor: uno abierto por profesor Y por tema (fase 2, 06-nov).

El profesor tiene dos cosas que revisar: su titulo y sus especializaciones. Cada una tiene su
ticket, para que el titulo (lo que lo habilita a hacer clases) no espere a las especializaciones.
Se mantiene la proteccion contra revisiones duplicadas del mismo tema.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Profesor
from soporte.models import Ticket
from soporte.tickets import abrir_ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_apoderados_pdf import bytes_pdf
from tests.test_soporte import crear_profesor
from user_profesor import titulo


class TicketPorTemaTests(TestCase):

    def setUp(self):
        self.agente_titulos = crear_agente('10000001-9', Ticket.TITULOS)
        self.agente_especializaciones = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        self.profesor = crear_profesor()
        titulo.subir(self.profesor, SimpleUploadedFile('titulo.pdf', bytes_pdf()))
        abrir_ticket(Ticket.ESPECIALIZACIONES, profesor=self.profesor)
        self.profesor.refresh_from_db()

    def abierto(self, categoria):
        return self.profesor.tickets.get(categoria=categoria, estado=Ticket.ABIERTO)

    def test_el_profesor_tiene_un_ticket_abierto_por_tema_cada_uno_con_su_agente(self):
        nombre = self.profesor.nombre
        self.assertEqual((self.abierto(Ticket.TITULOS).asignado, self.abierto(Ticket.TITULOS).asunto),
                         (self.agente_titulos, f'Título de {nombre}'))
        self.assertEqual((self.abierto(Ticket.ESPECIALIZACIONES).asignado,
                          self.abierto(Ticket.ESPECIALIZACIONES).asunto),
                         (self.agente_especializaciones, f'Especializaciones de {nombre}'))

    def test_no_se_duplica_la_revision_del_mismo_tema(self):
        abrir_ticket(Ticket.ESPECIALIZACIONES, profesor=self.profesor)
        self.assertEqual(self.profesor.tickets.filter(estado=Ticket.ABIERTO).count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():  # la base tampoco lo permite
            Ticket.objects.create(categoria=Ticket.ESPECIALIZACIONES, profesor=self.profesor, vence=timezone.now())

    def test_decidir_el_titulo_no_cierra_el_ticket_de_especializaciones(self):
        titulo.resolver(self.profesor, True)
        self.assertFalse(self.profesor.tickets.filter(categoria=Ticket.TITULOS, estado=Ticket.ABIERTO).exists())
        self.assertTrue(self.abierto(Ticket.ESPECIALIZACIONES))

    def test_el_ticket_de_especializaciones_no_da_acceso_al_titulo(self):
        ver = reverse('ver_titulo', args=[self.profesor.pk])
        entrar_soporte(self.client, self.agente_especializaciones)
        self.assertEqual(self.client.get(ver).status_code, 404)
        self.assertNotIn(self.profesor, self.client.get(reverse('titulos_adm')).context['en_revision'])
        self.client.post(reverse('resolver_titulo', args=[self.profesor.pk]), {'decision': 'aprobar'})
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_EN_REVISION)
        # control: el agente del ticket de titulo si lo ve
        entrar_soporte(self.client, self.agente_titulos)
        self.assertEqual(self.client.get(ver).status_code, 200)
        self.assertIn(self.profesor, self.client.get(reverse('titulos_adm')).context['en_revision'])
