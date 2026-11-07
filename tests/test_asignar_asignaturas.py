"""Soporte asigna asignaturas del catalogo al aprobar un titulo o una especializacion (fase 3, paso 2).

Especializacion: al menos una; las propuestas van premarcadas, pero puede elegir cualquiera del catalogo.
Titulo: opcional. Cada asignatura crea su Clase online y sin hora fija, sin duplicar, y la agenda le genera
bloques de inmediato. Datos ficticios.
"""

from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from agenda.models import HorarioSemanal
from alumnos.models import Asignatura, Clase, Especializacion, Profesor, SesionClase
from soporte.models import Ticket
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_especialidad import crear_profesor as crear_profesor_sin_especialidad
from tests.test_especializaciones_revision import pdf
from tests.test_soporte import crear_profesor
from user_profesor import especializaciones, titulo


class AsignarAsignaturasTests(TestCase):

    def setUp(self):
        crear_agente('10000001-9', Ticket.TITULOS)
        self.agente = crear_agente('10000002-7', Ticket.ESPECIALIZACIONES)
        self.profesor = crear_profesor()
        self.algebra, self.calculo, self.estadistica = (
            Asignatura.objects.create(nombre=n) for n in ('Álgebra', 'Cálculo', 'Estadística'))
        self.esp = especializaciones.subir(self.profesor, 'Diplomado', pdf('d.pdf'),
                                           [self.algebra.pk, self.calculo.pk])

    def materias(self):
        return set(Clase.objects.filter(profesor=self.profesor).values_list('asignatura__nombre', flat=True))

    def test_especializacion_crea_las_elegidas_aunque_no_sean_las_propuestas(self):
        # Propuso Algebra y Calculo; soporte deja Algebra, quita Calculo y suma Estadistica.
        nuevas = especializaciones.resolver(self.esp, True, ids_asignaturas=[self.algebra.pk, self.estadistica.pk])
        self.assertEqual(self.materias(), {'Álgebra', 'Estadística'})
        self.assertEqual(len(nuevas), 2)
        self.assertEqual({(c.modalidad, c.horario) for c in Clase.objects.all()}, {('online', None)})

    def test_especializacion_sin_asignaturas_o_con_una_ajena_no_se_aprueba(self):
        for ids in ([], ['999999'], [self.algebra.pk, 'x']):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                especializaciones.resolver(self.esp, True, ids_asignaturas=ids)
        self.esp.refresh_from_db()
        self.assertEqual(self.esp.estado, Especializacion.EN_REVISION)
        self.assertIsNotNone(self.esp.contenido)  # no se borro el documento
        self.assertEqual(self.materias(), set())

    def test_rechazar_no_asigna_nada(self):
        especializaciones.resolver(self.esp, False, 'Ilegible', ids_asignaturas=[self.algebra.pk])
        self.assertEqual(self.materias(), set())

    def test_no_duplica_una_clase_que_ya_tiene(self):
        Clase.objects.create(profesor=self.profesor, asignatura=self.algebra, modalidad='presencial')
        nuevas = especializaciones.resolver(self.esp, True, ids_asignaturas=[self.algebra.pk])
        self.assertEqual(nuevas, [])
        self.assertEqual(list(Clase.objects.values_list('modalidad', flat=True)), ['presencial'])  # no se toca

    def test_titulo_se_aprueba_con_o_sin_asignaturas(self):
        titulo.subir(self.profesor, pdf('t.pdf'))
        self.assertEqual(titulo.resolver(self.profesor, True), [])
        self.assertEqual(self.materias(), set())

        otro = crear_profesor_sin_especialidad('23333333-3', 'otro@lbwus.cl', None, Profesor.TITULO_PENDIENTE)
        titulo.subir(otro, pdf('t2.pdf'))
        titulo.resolver(otro, True, ids_asignaturas=[self.calculo.pk])
        self.assertEqual(list(Clase.objects.filter(profesor=otro).values_list('asignatura__nombre', flat=True)),
                         ['Cálculo'])

    def test_titulo_con_una_asignatura_ajena_no_se_aprueba(self):
        titulo.subir(self.profesor, pdf('t.pdf'))
        with self.assertRaises(ValidationError):
            titulo.resolver(self.profesor, True, ids_asignaturas=['999999'])
        self.profesor.refresh_from_db()
        self.assertEqual(self.profesor.titulo_estado, Profesor.TITULO_EN_REVISION)
        self.assertIsNotNone(self.profesor.titulo_contenido)

    def test_la_clase_nueva_ya_tiene_bloques_en_su_agenda(self):
        # Sin esto no aparece en el catalogo hasta el proximo cron (generar_bloques).
        HorarioSemanal.objects.create(profesor=self.profesor, dia_semana=0, hora_inicio=time(15), hora_fin=time(17))
        titulo.subir(self.profesor, pdf('t.pdf'))
        titulo.resolver(self.profesor, True, ids_asignaturas=[self.algebra.pk])
        self.assertTrue(SesionClase.objects.filter(clase__asignatura=self.algebra).exists())

    def test_en_la_pantalla_las_propuestas_van_premarcadas_y_el_mensaje_dice_cuales_quedaron(self):
        entrar_soporte(self.client, self.agente)
        pagina = self.client.get(reverse('titulos_adm'))
        self.assertContains(pagina, f'value="{self.algebra.pk}" checked>')
        self.assertContains(pagina, f'value="{self.calculo.pk}" checked>')
        self.assertContains(pagina, f'value="{self.estadistica.pk}">')  # del catalogo, sin marcar
        respuesta = self.client.post(reverse('resolver_especializacion', args=[self.esp.pk]),
                                     {'decision': 'aprobar', 'asignaturas': [self.estadistica.pk]}, follow=True)
        self.assertContains(respuesta, 'Asignaturas nuevas: Estadística.')
        self.assertEqual(self.materias(), {'Estadística'})
