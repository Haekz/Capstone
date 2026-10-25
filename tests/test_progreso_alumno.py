"""Vista "Mi Progreso" del portal del alumno: estadisticas reales, sin valores fijos.

Una clase completada es una inscripcion confirmada en una sesion que ya
termino y no se cancelo. Lo que aun no tiene modelo (calificaciones, avance
por ramo, grafico semanal y comentarios) se identifica como tal.
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Asignatura, Clase, Genero, Inscripcion, SesionClase
from tests.test_especialidad import CLAVE, NAC, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_suscripciones import dar_plan

User = get_user_model()

RUT_ANA = '11111111-1'


def crear_alumno(rut, nombre, genero):
    user = User.objects.create_user(
        rut, password=CLAVE, rol='alumno', rut=rut, first_name=nombre,
        email=f'{rut}@lbwus.cl', direccion='C1', fecha_nacimiento=NAC, genero=genero,
    )
    return Alumno.objects.create(user=user, nivel_educacion='media')


class ProgresoAlumnoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.ana = crear_alumno(RUT_ANA, 'Ana', genero)
        dar_plan(cls.ana)  # Mi Progreso es premium: sin plan no se renderiza
        cls.bea = crear_alumno('22222222-2', 'Bea', genero)
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)

        def clase(nombre_asignatura):
            asignatura = Asignatura.objects.create(nombre=nombre_asignatura)
            return Clase.objects.create(asignatura=asignatura, modalidad='online',
                                        horario=time(10, 0), profesor=profesor)

        algebra, fisica = clase('Álgebra'), clase('Física')

        def inscribir(alumno, sesion, estado=Inscripcion.ESTADO_CONFIRMADA):
            return Inscripcion.objects.create(alumno=alumno, clase=sesion.clase,
                                              sesion=sesion, estado=estado)

        # Cuentan: 2 de Algebra (1 h c/u) y 1 de Fisica (30 min) => 2.5 h, 3 clases, 2 ramos.
        alg_1, alg_2 = crear_sesion(algebra, dias=-3), crear_sesion(algebra, dias=-2)
        fis = crear_sesion(fisica, dias=-1)
        fis.fecha_hora_fin = fis.fecha_hora_inicio + timedelta(minutes=30)
        fis.save(skip_clean=True)
        cls.completadas = {inscribir(cls.ana, s) for s in (alg_1, alg_2, fis)}

        # No cuentan: pendiente, cancelada, sesion futura, sesion cancelada,
        # inscripcion sin sesion y la de otra alumna.
        inscribir(cls.ana, crear_sesion(algebra, dias=-4), Inscripcion.ESTADO_PENDIENTE)
        inscribir(cls.ana, crear_sesion(algebra, dias=-5), Inscripcion.ESTADO_CANCELADA)
        inscribir(cls.ana, crear_sesion(algebra, dias=2))
        cancelada = crear_sesion(fisica, dias=-6)
        cancelada.estado = SesionClase.ESTADO_CANCELADA
        cancelada.save(skip_clean=True)
        inscribir(cls.ana, cancelada)
        Inscripcion.objects.create(alumno=cls.ana, clase=fisica)
        inscribir(cls.bea, alg_1)

    def test_completadas_solo_confirmadas_en_sesiones_terminadas(self):
        self.assertEqual(set(Inscripcion.objects.filter(alumno=self.ana).completadas()),
                         self.completadas)

    def test_resumen_progreso_con_datos_reales(self):
        self.assertEqual(self.ana.resumen_progreso(),
                         {'horas': 2.5, 'clases': 3, 'ramos': 2})

    def test_resumen_progreso_sin_clases_completadas(self):
        nueva = crear_alumno('33333333-3', 'Caro', Genero.objects.get())
        self.assertEqual(nueva.resumen_progreso(), {'horas': 0, 'clases': 0, 'ramos': 0})

    def test_portal_muestra_estadisticas_reales_sin_valores_fijos(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.status_code, 200)

        self.assertContains(r, f'id="progress-stat-hours">{floatformat(2.5, "-1")} hrs<')
        self.assertContains(r, 'id="progress-stat-classes">3<')
        self.assertContains(r, 'id="progress-stat-subjects">2<')
        self.assertContains(r, 'id="progress-stat-rating">Sin datos<')
        for fijo in ('36.5 hrs', 'id="progress-stat-classes">24<',
                     'id="progress-stat-subjects">4<', 'id="progress-stat-rating">4.9<'):
            self.assertNotContains(r, fijo)

    def test_secciones_sin_modelo_marcadas_como_ejemplo(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        for aviso in ('el avance por ramo aún no se registra',
                      'el gráfico semanal aún no usa tus datos',
                      'los comentarios de docentes aún no se registran'):
            self.assertContains(r, f'Contenido de ejemplo: {aviso}')
