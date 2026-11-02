"""Seccion "Mi Agenda" del panel del profesor (paso B1c, decidido 02-nov). Datos ficticios."""

from datetime import time

from django.urls import reverse

from agenda.models import HorarioSemanal
from alumnos.models import SesionClase
from alumnos.services import InscripcionService
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete

LUNES = 0


class PanelAgendaTests(Escenario):

    def setUp(self):
        self.entrar(RUT_PROFE)

    def agregar(self, dia='0', desde='15:00', hasta='19:00'):
        return self.client.post(reverse('agenda_agregar_franja'),
                                {'dia_semana': dia, 'hora_inicio': desde, 'hora_fin': hasta}, follow=True)

    def test_el_panel_tiene_la_seccion_mi_agenda(self):
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, 'id="sec-agenda"')
        self.assertContains(r, 'id="menu-agenda"')

    def test_agregar_franja_crea_los_bloques_y_vuelve_al_panel(self):
        r = self.agregar()
        self.assertRedirects(r, reverse('panel_profesor'))
        self.assertContains(r, 'bloques nuevos en tu agenda')
        self.assertTrue(HorarioSemanal.objects.filter(profesor=self.profe, dia_semana=LUNES).exists())
        self.assertTrue(SesionClase.objects.filter(clase__profesor=self.profe).exists())

    def test_franja_invalida_avisa_y_no_se_guarda(self):
        self.assertContains(self.agregar(desde='15:30'), 'horas en punto')
        self.assertContains(self.agregar(dia='x'), 'Elige el día y las horas')
        self.assertFalse(HorarioSemanal.objects.exists())

    def test_solo_puede_quitar_sus_propias_franjas(self):
        ajena = HorarioSemanal.objects.create(profesor=self.otro, dia_semana=LUNES,
                                              hora_inicio=time(15), hora_fin=time(19))
        r = self.client.post(reverse('agenda_quitar_franja', args=[ajena.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(HorarioSemanal.objects.filter(pk=ajena.pk).exists())

    def test_quitar_su_franja(self):
        self.agregar()
        propia = HorarioSemanal.objects.get()
        self.client.post(reverse('agenda_quitar_franja', args=[propia.pk]))
        self.assertFalse(HorarioSemanal.objects.exists())

    def test_la_agenda_muestra_la_reserva_solo_con_el_nombre_de_pila(self):
        self.agregar()
        dar_paquete(self.ana, self.profe)
        InscripcionService.inscribir_alumno_en_sesion(self.ana, SesionClase.objects.first().pk)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, 'Ana · Algebra')
        for privado in filter(None, (RUT_ANA, self.ana.user.email, self.ana.user.last_name)):
            self.assertNotContains(r, privado)

    def test_un_alumno_no_puede_tocar_horarios(self):
        self.entrar(RUT_ANA)
        self.agregar()
        self.assertFalse(HorarioSemanal.objects.exists())

    def test_agregar_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('agenda_agregar_franja')).status_code, 405)
