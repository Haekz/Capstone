"""Soporte cambia el horario del profesor desde su ticket de Horario (fase 7, commit 2, decidido 07-nov).

Solo el agente asignado, con las mismas reglas que el profesor. Cada cambio queda como mensaje de soporte en el
ticket (registro y aviso al profesor); si el mensaje falla, el cambio no se guarda. Datos ficticios.
"""

from datetime import time
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse

from agenda.models import HorarioSemanal
from alumnos.models import Asignatura, Clase, SesionClase
from soporte.models import Ticket
from soporte.tickets import abrir_reporte
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_paquetes import Escenario

LUNES = 0


class SoporteCambiaElHorarioTests(Escenario):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.HORARIO, Ticket.CLASES)  # ve tambien los de Clases
        self.ticket = abrir_reporte(self.profe.user, Ticket.HORARIO, 'No s\u00e9 armar mi horario', 'Ayuda, porfa.')
        self.otro_agente = crear_agente('10000002-7', Ticket.HORARIO)  # habilitado, pero no lo tiene
        self.lider = crear_agente('10000003-5', lider=True)
        entrar_soporte(self.client, self.agente)

    def agregar(self, ticket=None, **cambios):
        datos = {'dia_semana': '0', 'hora_inicio': '15:00', 'hora_fin': '17:00', 'clase': '', **cambios}
        return self.client.post(reverse('soporte_agregar_franja', args=[(ticket or self.ticket).pk]), datos, follow=True)

    def quitar(self, franja, ticket=None):
        return self.client.post(reverse('soporte_quitar_franja', args=[(ticket or self.ticket).pk, franja.pk]),
                                follow=True)

    def franja(self, profesor=None, desde=15, hasta=19):
        return HorarioSemanal.objects.create(profesor=profesor or self.profe, dia_semana=LUNES,
                                             hora_inicio=time(desde), hora_fin=time(hasta))

    def mensajes(self):
        return list(self.ticket.mensajes.values_list('texto', 'de_soporte', 'autor'))

    def test_el_agente_asignado_agrega_una_franja_y_queda_registrado_en_el_ticket(self):
        r = self.agregar(clase=self.clase.pk)
        self.assertRedirects(r, reverse('soporte_reporte', args=[self.ticket.pk]))
        self.assertContains(r, 'Franja agregada. Se lo contamos al profesor en el ticket.')
        franja = HorarioSemanal.objects.get(profesor=self.profe)
        self.assertEqual((franja.clase, franja.hora_inicio, franja.hora_fin), (self.clase, time(15), time(17)))
        self.assertTrue(SesionClase.objects.filter(clase=self.clase).exists())  # sus bloques, como si lo hiciera el
        [(texto, de_soporte, autor)] = self.mensajes()
        self.assertTrue(texto.startswith('Agregamos a tu horario la franja del lunes de 15:00 a 17:00, Algebra: '))
        self.assertTrue(texto.endswith('bloques nuevos en tu agenda.'))
        self.assertEqual((de_soporte, autor), (True, self.agente.user.pk))
        self.ticket.refresh_from_db()
        self.assertIsNotNone(self.ticket.respondido)  # cuenta como respuesta: cumple el plazo

    def test_el_profesor_recibe_el_aviso_de_respuesta(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.agregar()
        self.assertEqual([m.to for m in mail.outbox], [[self.profe.user.email]])

    def test_quita_una_franja_y_queda_registrado(self):
        franja = self.franja()
        self.assertContains(self.quitar(franja), 'Franja quitada. Se lo contamos al profesor en el ticket.')
        self.assertFalse(HorarioSemanal.objects.exists())
        [(texto, _, _)] = self.mensajes()
        self.assertEqual(texto, 'Quitamos de tu horario la franja del lunes de 15:00 a 19:00, todas tus materias. '
                                'Las clases ya reservadas se mantienen en tu agenda.')

    def test_con_las_mismas_reglas_que_el_profesor(self):
        self.franja(desde=15, hasta=17)
        ajena = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Fisica'),
                                     modalidad='online', profesor=self.otro)
        self.assertContains(self.agregar(hora_inicio='16:00', hora_fin='18:00'), 'no puedes dictar dos materias a la vez')
        self.assertContains(self.agregar(hora_inicio='17:30', hora_fin='18:00'), 'horas en punto')
        self.assertContains(self.agregar(dia_semana='x'), 'Elige el d\u00eda y las horas')
        self.assertEqual(self.agregar(clase=ajena.pk).status_code, 404)
        self.assertEqual(HorarioSemanal.objects.count(), 1)
        self.assertEqual(self.mensajes(), [])  # lo que no se hizo no se registra

    def test_si_el_mensaje_falla_el_cambio_no_se_guarda(self):
        franja = self.franja()
        with mock.patch('agenda.views_soporte.agregar_mensaje', side_effect=ValidationError('Ese ticket ya est\u00e1 cerrado.')):
            self.assertContains(self.agregar(hora_inicio='19:00', hora_fin='20:00'), 'Ese ticket ya est\u00e1 cerrado.')
            with self.assertRaises(ValidationError):
                self.client.post(reverse('soporte_quitar_franja', args=[self.ticket.pk, franja.pk]))
        self.assertEqual(list(HorarioSemanal.objects.all()), [franja])

    def test_solo_el_agente_asignado_y_solo_en_el_ticket_abierto_de_horario(self):
        franja = self.franja()
        de_clases = abrir_reporte(self.profe.user, Ticket.CLASES, 'Otra cosa', 'Algo')
        Ticket.objects.filter(pk=de_clases.pk).update(asignado=self.agente)
        casos = [(self.otro_agente, self.ticket), (self.lider, self.ticket), (self.agente, de_clases)]
        for agente, ticket in casos:
            with self.subTest(agente=agente.nombre, categoria=ticket.categoria):
                self.client.logout()
                entrar_soporte(self.client, agente)
                self.assertEqual(self.agregar(ticket, hora_inicio='19:00', hora_fin='20:00').status_code, 404)
                self.assertEqual(self.quitar(franja, ticket).status_code, 404)
        self.client.logout()
        entrar_soporte(self.client, self.agente)
        Ticket.objects.filter(pk=self.ticket.pk).update(estado=Ticket.CERRADO)
        self.assertEqual(self.agregar(hora_inicio='19:00', hora_fin='20:00').status_code, 404)
        self.assertEqual(list(HorarioSemanal.objects.all()), [franja])

    def test_no_quita_franjas_de_otro_profesor(self):
        ajena = self.franja(profesor=self.otro)
        self.assertEqual(self.quitar(ajena).status_code, 404)
        self.assertTrue(HorarioSemanal.objects.filter(pk=ajena.pk).exists())

    def test_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('soporte_agregar_franja', args=[self.ticket.pk])).status_code, 405)

    def test_el_detalle_del_ticket_muestra_el_horario_y_los_botones_solo_al_asignado(self):
        self.franja()
        url = reverse('soporte_reporte', args=[self.ticket.pk])
        agregar = reverse('soporte_agregar_franja', args=[self.ticket.pk])
        r = self.client.get(url)
        self.assertContains(r, 'Horario del profesor')
        self.assertContains(r, f'action="{agregar}"')
        self.assertContains(r, '<td>Todas sus materias</td>', html=True)
        self.client.logout()
        entrar_soporte(self.client, self.lider)  # el lider lo ve, pero no lo tiene asignado
        r = self.client.get(url)
        self.assertContains(r, 'Horario del profesor')
        self.assertNotContains(r, f'action="{agregar}"')
        self.assertContains(r, 'Solo el agente asignado cambia el horario.')

    def test_un_ticket_de_otra_categoria_no_muestra_el_horario(self):
        de_clases = abrir_reporte(self.profe.user, Ticket.CLASES, 'Otra cosa', 'Algo')
        Ticket.objects.filter(pk=de_clases.pk).update(asignado=self.agente)
        self.assertNotContains(self.client.get(reverse('soporte_reporte', args=[de_clases.pk])), 'Horario del profesor')
