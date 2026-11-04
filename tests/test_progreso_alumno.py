"""Vista "Mi Progreso" del portal del alumno: estadisticas reales, sin valores fijos.

Una clase completada es una inscripcion confirmada en una sesion que ya
termino y no se cancelo. Lo que aun no tiene modelo (calificaciones, avance
por ramo, grafico semanal y comentarios) se identifica como tal.
"""

from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.template.defaultfilters import floatformat
from django.test import TestCase
from django.urls import reverse

from alumnos import progreso
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
        self.assertNotContains(r, 'progress-stat-rating')  # no hay fuente de datos: se retiro el cuadro, no se inventa
        self.assertNotContains(r, 'Promedio Feedback')
        for fijo in ('36.5 hrs', 'id="progress-stat-classes">24<',
                     'id="progress-stat-subjects">4<'):
            self.assertNotContains(r, fijo)

    def test_mi_progreso_ya_no_tiene_secciones_de_ejemplo(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        for ejemplo in ('el avance por ramo aún no se registra', 'el gráfico semanal aún no usa tus datos',
                        'los comentarios de docentes aún no se registran', 'Sem 1', 'M 40 170 Q 110 120'):
            self.assertNotContains(r, ejemplo)

    def test_grafico_semanal_suma_las_horas_reales_de_las_ultimas_cinco_semanas(self):
        algebra = Clase.objects.get(asignatura__nombre='Álgebra')
        # Fuera de la ventana de 5 semanas: no cuenta.
        Inscripcion.objects.create(alumno=self.ana, clase=algebra, sesion=crear_sesion(algebra, dias=-40),
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        semanas = progreso.horas_por_semana(self.ana)
        self.assertEqual(len(semanas), 5)
        self.assertEqual(sum(s['horas'] for s in semanas), 2.5)  # 2 de Álgebra + 1 de Física de media hora
        self.assertEqual([s['desde'].weekday() for s in semanas], [0] * 5)  # cada semana parte un lunes
        self.assertEqual([s['desde'] for s in semanas], sorted(s['desde'] for s in semanas))
        self.assertEqual(max(s['y'] for s in semanas if s['horas'] == 0), progreso.Y_BASE)
        self.assertEqual(min(s['y'] for s in semanas), progreso.Y_TOPE)  # la mejor semana llega arriba
        self.assertEqual((semanas[0]['x'], semanas[-1]['x']), (progreso.X_INICIO, progreso.X_FIN))

    def test_grafico_semanal_pone_cada_clase_en_su_semana(self):
        algebra = Clase.objects.get(asignatura__nombre='Álgebra')
        caro = crear_alumno('33333333-3', 'Caro', Genero.objects.get())
        for dias in (-7, -14, -40):  # semana anterior, la previa y una fuera de la ventana
            Inscripcion.objects.create(alumno=caro, clase=algebra, sesion=crear_sesion(algebra, dias=dias),
                                       estado=Inscripcion.ESTADO_CONFIRMADA)
        semanas = progreso.horas_por_semana(caro)
        self.assertEqual([s['horas'] for s in semanas], [0, 0, 1.0, 1.0, 0])
        self.assertEqual([s['y'] for s in semanas], [progreso.Y_BASE, progreso.Y_BASE, progreso.Y_TOPE, progreso.Y_TOPE,
                                                    progreso.Y_BASE])

    def test_grafico_semanal_usa_el_lunes_de_hoy_como_ultima_semana(self):
        hoy = date(2026, 11, 4)  # miércoles; esa semana parte el lunes 2
        semanas = progreso.horas_por_semana(self.bea, hoy=hoy)
        self.assertEqual([s['desde'] for s in semanas], [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19),
                                                         date(2026, 10, 26), date(2026, 11, 2)])

    def test_grafico_semanal_sin_clases_queda_plano(self):
        semanas = progreso.horas_por_semana(crear_alumno('33333333-3', 'Caro', Genero.objects.get()))
        self.assertEqual([s['horas'] for s in semanas], [0] * 5)
        self.assertEqual({s['y'] for s in semanas}, {progreso.Y_BASE})

    def test_el_portal_dibuja_el_grafico_con_texto_alternativo(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, 'role="img" aria-label="Horas de estudio por semana: semana del ')
        self.assertContains(r, '<polyline')

    def test_avance_por_ramo_con_clases_y_horas_reales_del_mas_al_menos_estudiado(self):
        self.assertEqual(progreso.por_ramo(self.ana), [
            {'nombre': 'Álgebra', 'clases': 2, 'horas': 2.0, 'porcentaje': 100},
            {'nombre': 'Física', 'clases': 1, 'horas': 0.5, 'porcentaje': 25},
        ])

    def test_avance_por_ramo_solo_cuenta_las_clases_de_esa_alumna(self):
        bea = Alumno.objects.get(user__rut='22222222-2')
        self.assertEqual(progreso.por_ramo(bea), [{'nombre': 'Álgebra', 'clases': 1, 'horas': 1.0, 'porcentaje': 100}])

    def test_avance_por_ramo_sin_clases_completadas_esta_vacio(self):
        self.assertEqual(progreso.por_ramo(crear_alumno('33333333-3', 'Caro', Genero.objects.get())), [])

    def test_el_portal_muestra_el_avance_real_y_no_los_ramos_inventados(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, f'2 clases · {floatformat(2.0, "-1")} h')
        self.assertContains(r, f'1 clase · {floatformat(0.5, "-1")} h')
        self.assertContains(r, 'width: 100%')
        self.assertContains(r, 'width: 25%')
        for inventado in ('Matemáticas (Álgebra y Cálculo)', 'Programación (Python y Web)', 'Mecánica y Ondas', 'myClasses',
                          'subjectProgress', 'myReports'):
            self.assertNotContains(r, inventado)

    def test_sin_clases_el_portal_lo_dice_en_vez_de_mostrar_ramos(self):
        nueva = crear_alumno('33333333-3', 'Caro', Genero.objects.get())
        dar_plan(nueva)
        self.client.post(reverse('login'), {'username': '33333333-3', 'password': CLAVE})
        self.assertContains(self.client.get(reverse('alumno_pag1')), 'Aún no completas clases')
