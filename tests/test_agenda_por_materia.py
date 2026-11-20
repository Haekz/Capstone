"""Cada franja del horario puede ser de una materia (fase 6, commit 1, decidido 07-nov).

El profesor elige la materia por franja y las franjas no se cruzan, sean de la misma materia o no. Las franjas
que ya existian (sin materia) siguen valiendo para todas sus materias. Datos ficticios.
"""

from datetime import time

from django.core.exceptions import ValidationError
from django.urls import reverse

from agenda.models import HorarioSemanal
from alumnos.models import Asignatura, Clase, SesionClase
from tests.test_paquetes import RUT_PROFE, Escenario

LUNES = 0


class FranjaPorMateriaTests(Escenario):

    def setUp(self):
        self.algebra = self.clase
        self.calculo = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Calculo'),
                                            modalidad='online', profesor=self.profe)
        self.entrar(RUT_PROFE)

    def agregar(self, clase=None, desde='15:00', hasta='17:00'):
        datos = {'dia_semana': '0', 'hora_inicio': desde, 'hora_fin': hasta}
        if clase is not None:
            datos['clase'] = clase.pk
        return self.client.post(reverse('agenda_agregar_franja'), datos, follow=True)

    def horas(self, clase):
        return {s.inicio_local.hour for s in SesionClase.objects.filter(clase=clase)}

    def test_una_franja_de_una_materia_solo_genera_bloques_de_esa_materia(self):
        self.assertContains(self.agregar(self.algebra), 'bloques nuevos en tu agenda')
        self.assertEqual(self.horas(self.algebra), {15, 16})
        self.assertFalse(SesionClase.objects.filter(clase=self.calculo).exists())
        self.assertEqual(HorarioSemanal.objects.get().clase, self.algebra)

    def test_cada_materia_con_su_propio_horario(self):
        self.agregar(self.algebra, '15:00', '17:00')
        self.agregar(self.calculo, '17:00', '19:00')
        self.assertEqual((self.horas(self.algebra), self.horas(self.calculo)), ({15, 16}, {17, 18}))

    def test_sin_materia_vale_para_todas_como_hasta_ahora(self):
        self.agregar()
        self.assertEqual((self.horas(self.algebra), self.horas(self.calculo)), ({15, 16}, {15, 16}))
        self.assertIsNone(HorarioSemanal.objects.get().clase)

    def test_las_franjas_no_se_cruzan_aunque_sean_de_materias_distintas(self):
        self.agregar(self.algebra, '15:00', '17:00')
        for clase in (self.calculo, self.algebra, None):
            with self.subTest(clase=clase):
                self.assertContains(self.agregar(clase, '16:00', '18:00'), 'no puedes dictar dos materias a la vez')
        self.assertEqual(HorarioSemanal.objects.count(), 1)
        self.agregar(self.calculo, '17:00', '19:00')  # pegadas, sin cruzarse: si
        self.assertEqual(HorarioSemanal.objects.count(), 2)

    def test_no_puede_elegir_la_materia_de_otro_profesor(self):
        ajena = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Fisica'),
                                     modalidad='online', profesor=self.otro)
        self.assertEqual(self.client.post(reverse('agenda_agregar_franja'), {
            'dia_semana': '0', 'hora_inicio': '15:00', 'hora_fin': '17:00', 'clase': ajena.pk}).status_code, 404)
        self.assertFalse(HorarioSemanal.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'Elige una de tus materias'):  # tambien en el modelo
            HorarioSemanal(profesor=self.profe, clase=ajena, dia_semana=LUNES,
                           hora_inicio=time(15), hora_fin=time(17)).full_clean()

    def test_una_materia_invalida_no_guarda_nada(self):
        r = self.client.post(reverse('agenda_agregar_franja'), {
            'dia_semana': '0', 'hora_inicio': '15:00', 'hora_fin': '17:00', 'clase': 'x'}, follow=True)
        self.assertContains(r, 'Elige el día y las horas')
        self.assertFalse(HorarioSemanal.objects.exists())

    def test_el_panel_muestra_la_materia_de_cada_franja_y_solo_ofrece_las_propias(self):
        Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Fisica'),
                             modalidad='online', profesor=self.otro)
        self.agregar(self.algebra, '15:00', '17:00')
        HorarioSemanal.objects.create(profesor=self.profe, dia_semana=1, hora_inicio=time(9), hora_fin=time(11))
        html = self.client.get(reverse('panel_profesor')).content.decode()
        self.assertIn('<th>Materia</th>', html)
        self.assertIn('<td>Algebra</td>', html)
        self.assertIn('<td>Todas mis materias</td>', html)  # la franja de antes
        self.assertIn(f'<option value="{self.calculo.pk}">Calculo</option>', html)
        self.assertNotIn('>Fisica</option>', html)
