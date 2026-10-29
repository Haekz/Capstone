"""Filtros combinados del catalogo de clases (especialidad, modalidad, disponibilidad).

Una clase esta disponible si tiene
al menos una SesionClase programada, futura y con cupo (SesionClase.disponibles).
Solo se ofrecen clases de profesores con titulo aprobado.
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import (
    Alumno, Asignatura, Clase, Especialidad, Genero, Inscripcion, Profesor, SesionClase,
)
from tests.test_especialidad import CLAVE, NAC, crear_profesor

User = get_user_model()

RUT_ALUMNO = '11111111-1'


def crear_sesion(clase, dias, cupo=5, estado=SesionClase.ESTADO_PROGRAMADA):
    """Sesion de 1 hora a `dias` dias de hoy (negativo = en el pasado)."""
    inicio = timezone.now() + timedelta(days=dias)
    sesion = SesionClase(clase=clase, fecha_hora_inicio=inicio,
                         fecha_hora_fin=inicio + timedelta(hours=1),
                         cupo_maximo=cupo, estado=estado)
    sesion.save(skip_clean=dias < 0)  # clean() exige fecha futura al crear
    return sesion


class EscenarioCatalogo(TestCase):
    """4 clases habilitadas que cubren cada combinacion, mas 1 de profesor sin titulo."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.alumno = Alumno.objects.create(
            user=User.objects.create_user(
                RUT_ALUMNO, password=CLAVE, rol='alumno', rut=RUT_ALUMNO,
                first_name='Ana', email='alumna@lbwus.cl', direccion='C1',
                fecha_nacimiento=NAC, genero=genero,
            ),
            nivel_educacion='media',
        )
        cls.mat = Especialidad.objects.create(nombre='Matemáticas')
        cls.ing = Especialidad.objects.create(nombre='Inglés')
        prof_mat = crear_profesor('20000000-1', 'mat@lbwus.cl', cls.mat)
        prof_ing = crear_profesor('20000000-2', 'ing@lbwus.cl', cls.ing)
        prof_pendiente = crear_profesor('20000000-3', 'pen@lbwus.cl', cls.mat,
                                        Profesor.TITULO_PENDIENTE)
        asignatura = Asignatura.objects.create(nombre='Álgebra')

        def clase(profesor, modalidad):
            return Clase.objects.create(asignatura=asignatura, modalidad=modalidad,
                                        horario=time(10, 0), profesor=profesor)

        # Matematicas online: dos sesiones con cupo (debe salir una sola vez).
        cls.mat_online = clase(prof_mat, 'online')
        crear_sesion(cls.mat_online, dias=1)
        crear_sesion(cls.mat_online, dias=2)
        # Matematicas presencial: sin sesiones.
        cls.mat_presencial = clase(prof_mat, 'presencial')
        # Ingles online: solo sesiones que NO cuentan (llena, cancelada y pasada).
        cls.ing_online = clase(prof_ing, 'online')
        llena = crear_sesion(cls.ing_online, dias=1, cupo=1)
        Inscripcion.objects.create(alumno=cls.alumno, clase=cls.ing_online, sesion=llena)
        crear_sesion(cls.ing_online, dias=2, estado=SesionClase.ESTADO_CANCELADA)
        crear_sesion(cls.ing_online, dias=-1)
        # Ingles presencial: con cupo.
        cls.ing_presencial = clase(prof_ing, 'presencial')
        crear_sesion(cls.ing_presencial, dias=3)
        # Profesor sin titulo aprobado: nunca se ofrece, aunque tenga cupo.
        cls.de_pendiente = clase(prof_pendiente, 'online')
        crear_sesion(cls.de_pendiente, dias=1)

        cls.habilitadas = {cls.mat_online, cls.mat_presencial,
                           cls.ing_online, cls.ing_presencial}


class ClaseQuerySetTests(EscenarioCatalogo):

    def test_habilitadas_excluye_profesor_sin_titulo_aprobado(self):
        self.assertEqual(set(Clase.objects.habilitadas()), self.habilitadas)

    def test_disponibilidad_efectiva_segun_sesiones(self):
        # Sin sesiones, llena, cancelada o pasada => no disponible.
        self.assertEqual(set(Clase.objects.habilitadas().con_disponibilidad()),
                         {self.mat_online, self.ing_presencial})

    def test_varias_sesiones_disponibles_no_duplican_la_clase(self):
        clases = list(Clase.objects.habilitadas().con_disponibilidad())
        self.assertEqual(clases.count(self.mat_online), 1)

    def test_filtros_combinados(self):
        casos = [
            ({}, self.habilitadas),
            ({'especialidad': self.mat}, {self.mat_online, self.mat_presencial}),
            ({'modalidad': 'online'}, {self.mat_online, self.ing_online}),
            ({'solo_disponibles': True}, {self.mat_online, self.ing_presencial}),
            ({'especialidad': self.ing, 'modalidad': 'presencial'}, {self.ing_presencial}),
            ({'especialidad': self.mat, 'modalidad': 'online', 'solo_disponibles': True},
             {self.mat_online}),
            # Combinaciones sin resultados.
            ({'especialidad': self.ing, 'modalidad': 'online', 'solo_disponibles': True}, set()),
            ({'especialidad': self.mat, 'modalidad': 'presencial', 'solo_disponibles': True},
             set()),
        ]
        for filtros, esperado in casos:
            with self.subTest(**{k: str(v) for k, v in filtros.items()}):
                self.assertEqual(set(Clase.objects.habilitadas().filtrar(**filtros)), esperado)


class CatalogoInterfazTests(EscenarioCatalogo):

    def setUp(self):
        self.client.post(reverse('login'), {'username': RUT_ALUMNO, 'password': CLAVE})

    def _portal(self, **params):
        r = self.client.get(reverse('alumno_pag1'), params)
        self.assertEqual(r.status_code, 200)
        return r

    def _ids(self, respuesta):
        return {c.id_clase for c in respuesta.context['clases_disponibles']}

    def assertMuestraClases(self, respuesta, clases):
        self.assertEqual(self._ids(respuesta), {c.id_clase for c in clases})
        for c in clases:
            self.assertContains(respuesta, f'abrirModalHorarios({c.id_clase},')

    def test_sin_filtros_muestra_solo_clases_habilitadas(self):
        r = self._portal()
        self.assertMuestraClases(r, self.habilitadas)
        self.assertNotContains(r, f'abrirModalHorarios({self.de_pendiente.id_clase},')
        self.assertFalse(r.context['hay_filtros'])
        self.assertNotContains(r, 'Limpiar filtros')

    def test_opciones_de_filtro_salen_del_backend(self):
        r = self._portal()
        self.assertContains(r, f'<option value="{self.mat.pk}">Matemáticas</option>', html=True)
        self.assertContains(r, f'<option value="{self.ing.pk}">Inglés</option>', html=True)
        self.assertContains(r, '<option value="online">Online</option>', html=True)
        self.assertContains(r, '<option value="presencial">Presencial</option>', html=True)
        self.assertContains(r, 'Solo con horarios y cupos disponibles')

    def test_filtro_combinado_y_estado_conservado(self):
        r = self._portal(especialidad=self.mat.pk, modalidad='online', disponible='on')
        self.assertMuestraClases(r, [self.mat_online])
        self.assertContains(
            r, f'<option value="{self.mat.pk}" selected>Matemáticas</option>', html=True)
        self.assertContains(r, '<option value="online" selected>Online</option>', html=True)
        self.assertContains(
            r, '<input type="checkbox" name="disponible" id="filtro-disponible" checked>',
            html=True)
        self.assertContains(r, 'Limpiar filtros')
        # Tras recargar, el JS vuelve a la vista del catalogo.
        self.assertContains(r, 'requestClassAccess();  // vuelve al catalogo tras filtrar')

    def test_combinacion_sin_resultados_muestra_mensaje(self):
        r = self._portal(especialidad=self.ing.pk, modalidad='online', disponible='on')
        self.assertMuestraClases(r, [])
        self.assertContains(r, 'No hay clases que coincidan con los filtros seleccionados.')
        self.assertNotContains(r, 'No hay clases abiertas disponibles en este momento.')

    def test_valores_invalidos_se_ignoran_sin_romper(self):
        for params in ({'especialidad': '9999'}, {'especialidad': 'abc'},
                       {'modalidad': '<script>'}):
            with self.subTest(**params):
                self.assertMuestraClases(self._portal(**params), self.habilitadas)

    def test_etiquetas_de_temas_salen_del_catalogo(self):
        r = self._portal()
        self.assertContains(r, 'data-topic="Matemáticas"')
        self.assertContains(r, 'data-topic="Inglés"')
        # Las etiquetas fijas que no existen en la base ya no aparecen.
        for fija in ('Historia', 'Programación'):
            self.assertNotContains(r, f'data-topic="{fija}"')

    def test_nombres_del_catalogo_salen_escapados(self):
        Especialidad.objects.create(nombre='<b>Hack</b>')
        r = self._portal()
        self.assertNotContains(r, '<b>Hack</b>')
        self.assertContains(r, '&lt;b&gt;Hack&lt;/b&gt;')
