"""Prerrequisitos de seguridad antes de admitir menores (decisiones 1, 7 y 10).

- Sala virtual: solo el profesor de la clase y el alumno con inscripcion valida.
  Ni administradores, ni staff, ni el campo ``rol`` abren clases ajenas.
- Una sola regla de edad para los tres caminos de alta de alumnos. Sigue en 18
  hasta que exista el modulo de apoderados.

S-03 (clave inicial = RUT) lo corrige la rama de Franco (S4-02), no esta.
"""

from datetime import date, time
from functools import partial

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from admin_portal.forms import AdminAlumnoForm
from alumnos.forms import AlumnoForm
from alumnos.google_forms import CompletarRegistroGoogleForm
from alumnos.models import Asignatura, Clase, Genero, Inscripcion, Tutor
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
MENOR = date(date.today().year - 17, 1, 1).isoformat()
ADULTO = '2000-01-01'


class SalaVirtualSoloParticipantesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=time(10, 0), profesor=cls.profesor)
        cls.ana = crear_alumno('11111111-1', 'Ana', genero)
        Inscripcion.objects.create(alumno=cls.ana, clase=cls.clase, sesion=crear_sesion(cls.clase, dias=2),
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        cls.admin = User.objects.create_user('10101010-1', password=CLAVE, rol='admin')
        cls.tutor = Tutor.objects.create(user=cls.admin)

    def abrir_sala(self, user, **sesion_extra):
        self.client.force_login(user)
        sesion = self.client.session
        sesion.update(sesion_extra)
        sesion.save()
        return self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))

    def test_entran_el_profesor_de_la_clase_y_la_alumna_inscrita(self):
        self.assertEqual(self.abrir_sala(self.profesor.user).status_code, 200)
        self.assertEqual(self.abrir_sala(self.ana.user).status_code, 200)

    def test_otro_profesor_no_entra(self):
        otro = crear_profesor('30000000-2', 'otro@lbwus.cl', None)
        self.assertEqual(self.abrir_sala(otro.user).status_code, 403)

    def test_administrador_no_entra_a_clases_ajenas(self):
        self.assertEqual(self.abrir_sala(self.admin, admin_id=self.tutor.id_tutor).status_code, 403)

    def test_staff_superusuario_o_campo_rol_no_abren_la_sala(self):
        casos = {
            'staff': dict(is_staff=True),
            'superusuario': dict(is_staff=True, is_superuser=True),
            'rol tutor': dict(rol='tutor'),
            'rol admin sin perfil': dict(rol='admin'),
        }
        for i, (nombre, extra) in enumerate(casos.items()):
            with self.subTest(nombre):
                user = User.objects.create_user(f'4000000{i}-0', password=CLAVE, **extra)
                self.assertEqual(self.abrir_sala(user, tutor_id=1).status_code, 403)


class MismaReglaDeEdadTests(TestCase):
    """Registro publico, Google y portal admin rechazan igual a un menor de 18."""

    FORMULARIOS = {
        'registro publico': AlumnoForm,
        'registro con Google': partial(CompletarRegistroGoogleForm, correo='google@demo.cl'),
        'portal admin': AdminAlumnoForm,
    }

    def error_de_fecha(self, formulario, fecha):
        form = formulario(data={'fecha_nacimiento': fecha})
        form.is_valid()
        return form.errors.get('fecha_nacimiento')

    def test_los_tres_caminos_rechazan_a_un_menor(self):
        for nombre, formulario in self.FORMULARIOS.items():
            with self.subTest(nombre):
                self.assertEqual(self.error_de_fecha(formulario, MENOR),
                                 ['Debes ser mayor o igual a 18 años.'])

    def test_los_tres_caminos_aceptan_a_un_adulto(self):
        for nombre, formulario in self.FORMULARIOS.items():
            with self.subTest(nombre):
                self.assertIsNone(self.error_de_fecha(formulario, ADULTO))
