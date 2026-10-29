"""Perfil profesional del profesor, con informacion real y privacidad.

Solo profesores habilitados. Se muestran datos profesionales; el telefono solo
si el profesor lo autorizo. Nunca RUT, correo, direccion ni fecha de nacimiento.
"""

from datetime import time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Asignatura, Clase, Especialidad, Genero, Profesor, SesionClase
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

RUT_ANA = '11111111-1'
RUT_PROFE = '20000000-1'


class PerfilProfesorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        cls.matematicas = Especialidad.objects.create(nombre='Matemáticas')
        cls.profe = crear_profesor(RUT_PROFE, 'profe@lbwus.cl', cls.matematicas)
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                     modalidad='online', horario=time(10, 0), profesor=cls.profe)
        cls.futura = crear_sesion(clase, dias=3)
        crear_sesion(clase, dias=-2)  # realizada: cuenta
        crear_sesion(clase, dias=-1, estado=SesionClase.ESTADO_CANCELADA)  # cancelada: no cuenta
        cls.en_revision = crear_profesor('20000000-2', 'otro@lbwus.cl', cls.matematicas,
                                         titulo_estado=Profesor.TITULO_EN_REVISION)

    def _perfil(self, profesor=None):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        return self.client.get(reverse('perfil_profesor', args=[(profesor or self.profe).id_profesor]))

    def test_muestra_informacion_profesional_real(self):
        r = self._perfil()
        self.assertEqual(r.status_code, 200)
        for dato in ('Profe', 'Matemáticas', 'Título profesional verificado', 'Álgebra'):
            self.assertContains(r, dato)
        self.assertEqual(r.context['sesiones_realizadas'], 1)
        self.assertEqual(list(r.context['proximas_sesiones']), [self.futura])
        self.assertContains(r, timezone.localtime(self.futura.fecha_hora_inicio).strftime('%d/%m/%Y'))

    def test_nunca_expone_datos_personales(self):
        r = self._perfil()
        for privado in (RUT_PROFE, 'profe@lbwus.cl', 'Calle 1', '911111111'):
            self.assertNotContains(r, privado)
        self.assertContains(r, 'No publicado por el profesor')

    def test_telefono_visible_solo_si_el_profesor_lo_autoriza(self):
        Profesor.objects.filter(pk=self.profe.pk).update(telefono_publico=True)
        self.assertContains(self._perfil(), 'href="tel:911111111"')

    def test_profesor_sin_titulo_aprobado_no_tiene_perfil(self):
        self.assertEqual(self._perfil(self.en_revision).status_code, 404)

    def test_requiere_sesion_de_alumno(self):
        r = self.client.get(reverse('perfil_profesor', args=[self.profe.id_profesor]))
        self.assertNotEqual(r.status_code, 200)

    def test_reservar_lleva_al_catalogo_filtrado_por_su_especialidad(self):
        self.assertContains(self._perfil(),
                            f'?especialidad={self.matematicas.id}&amp;disponible=on')

    def test_tarjetas_de_profesores_del_portal_enlazan_al_perfil(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, f'const URL_PERFIL_PROFESOR = "{reverse("perfil_profesor", args=[0])}"')
        # Modal, dashboard y favoritos; los tutores (de ejemplo) no tienen perfil.
        self.assertContains(r, '${enlacePerfil(t)}', count=3)
