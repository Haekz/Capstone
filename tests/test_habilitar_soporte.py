"""habilitar_soporte: cambia los temas de un agente que ya existe (p. ej. Contacto, H14). Datos ficticios."""

from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from admin_portal.models import MensajeContacto
from soporte.models import Ticket
from soporte.tickets import abrir_contacto, abrir_reporte
from tests.test_apoderados import crear_agente
from tests.test_soporte_reportes import crear_alumno_adulto


class HabilitarSoporteTests(TestCase):

    def setUp(self):
        self.agente = crear_agente('11111111-1', Ticket.TECNICO, Ticket.OTRO)

    def habilitar(self, *argumentos):
        salida = StringIO()
        call_command('habilitar_soporte', *argumentos, stdout=salida)
        return salida.getvalue()

    def test_agrega_y_quita_temas_con_el_rut_con_puntos(self):
        salida = self.habilitar('11.111.111-1', '--agregar', 'contacto', 'otro', '--quitar', 'tecnico')
        self.assertEqual(self.agente.categorias, {Ticket.OTRO, Ticket.CONTACTO})
        self.assertIn('ahora atiende: Contacto del sitio, Otro.', salida)

    def test_desde_ahi_recibe_los_tickets_del_tema(self):
        self.habilitar('11111111-1', '--agregar', 'contacto')
        ticket = abrir_contacto(MensajeContacto(nombre='Ana', correo='ana@example.com', mensaje='Hola'))
        self.assertEqual(ticket.asignado, self.agente)

    def test_avisa_si_deja_tickets_abiertos_del_tema_que_quita(self):
        abrir_reporte(crear_alumno_adulto().user, Ticket.TECNICO, 'No carga', 'Detalle.')
        self.assertIn('Tiene 1 ticket(s) abierto(s)', self.habilitar('11111111-1', '--quitar', 'tecnico'))

    def test_errores_sin_cambiar_nada(self):
        casos = ((['11111111-1'], 'Indica --agregar o --quitar'),
                 (['11111111-1', '--agregar', 'otro', '--quitar', 'otro'], 'a la vez'),
                 (['22222222-2', '--agregar', 'otro'], 'No hay un agente de soporte con ese RUT'))
        for argumentos, error in casos:
            with self.subTest(argumentos=argumentos), self.assertRaisesMessage(CommandError, error):
                self.habilitar(*argumentos)
        self.assertEqual(self.agente.categorias, {Ticket.TECNICO, Ticket.OTRO})
