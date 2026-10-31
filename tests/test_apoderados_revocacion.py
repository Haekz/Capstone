"""Revocar el vinculo y transicion al cumplir 18.

Datos ficticios. Revocan el apoderado (desde su cuenta) y el administrador (con
motivo obligatorio); se cancelan solo las clases futuras pagadas con ese
vinculo. A los 18 el vinculo termina solo y, si el apoderado definio la
contrasena, el estudiante debe elegir una nueva antes de seguir.
"""

from datetime import time as hora

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Asignatura, Clase, Inscripcion, Tutor
from apoderados.models import Apoderado, ClaveDelApoderado, CompraApoderado, Revocacion, Vinculo
from tests.test_apoderados import CLAVE, RUT, crear_apoderado, entrar
from tests.test_apoderados_adolescentes import datos_adolescente
from tests.test_apoderados_vinculos import RUT_NINO, crear_menor_vinculado, datos_estudiante, hace_anios
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import dar_paquete

User = get_user_model()
NUEVA = {'new_password1': 'Pelicano-Verde-2026', 'new_password2': 'Pelicano-Verde-2026'}


class RevocacionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Historia'),
                                     modalidad='online', horario=hora(10, 0), profesor=profesor)
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.madre)
        menor = cls.vinculo.alumno
        cls.padre = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        cls.vinculo_padre = Vinculo.objects.create(
            apoderado=cls.padre, alumno=menor, parentesco='padre', estado=Vinculo.VERIFICADO,
            version_declaracion=cls.vinculo.version_declaracion, declaracion_aceptada=cls.vinculo.declaracion_aceptada)
        cls.reservas = {}
        for nombre, apoderado, vinculo, dias in (('madre', cls.madre, cls.vinculo, 2),
                                                 ('padre', cls.padre, cls.vinculo_padre, 3)):
            paquete = dar_paquete(menor, profesor)
            CompraApoderado.objects.create(paquete=paquete, apoderado=apoderado, vinculo=vinculo)
            cls.reservas[nombre] = Inscripcion.objects.create(alumno=menor, clase=clase, paquete=paquete,
                                                              sesion=crear_sesion(clase, dias=dias))

    def setUp(self):
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)

    def revocar(self, vinculo=None, **datos):
        return self.client.post(reverse('apoderado_revocar_vinculo', args=[(vinculo or self.vinculo).pk]),
                                {'confirmar': 'on', **datos})

    def estado(self, nombre):
        self.reservas[nombre].refresh_from_db()
        return self.reservas[nombre].estado

    def test_se_desvincula_y_se_cancelan_solo_las_clases_que_pago(self):
        self.assertRedirects(self.revocar(), reverse('portal_apoderado'))
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.REVOCADO)
        self.assertEqual((self.vinculo.revocacion.autor, self.vinculo.revocacion.motivo), (self.madre.user, ''))
        self.assertEqual((self.estado('madre'), self.estado('padre')),
                         (Inscripcion.ESTADO_CANCELADA, Inscripcion.ESTADO_CONFIRMADA))
        clases = reverse('apoderado_clases_estudiante', args=[self.vinculo.pk])
        self.assertEqual(self.client.get(clases).status_code, 404)

    def test_sin_confirmar_no_revoca(self):
        self.client.post(reverse('apoderado_revocar_vinculo', args=[self.vinculo.pk]))
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.VERIFICADO)

    def test_no_revoca_el_vinculo_de_otro_ni_uno_ya_revocado(self):
        self.assertEqual(self.revocar(self.vinculo_padre).status_code, 404)
        self.revocar()
        self.assertEqual(self.revocar().status_code, 404)
        self.assertEqual(Revocacion.objects.count(), 1)
        self.assertEqual(self.estado('padre'), Inscripcion.ESTADO_CONFIRMADA)

    def test_el_administrador_revoca_solo_con_motivo(self):
        admin = User.objects.create_user('10101010-1', password=CLAVE, rol='admin', first_name='Admin')
        entrar(self.client, admin, admin_id=Tutor.objects.create(user=admin).id_tutor)
        url = reverse('apoderados_revocar_vinculo', args=[self.vinculo.pk])
        self.client.post(url, {'confirmar': 'on'})
        self.assertFalse(Revocacion.objects.exists())
        self.client.post(url, {'confirmar': 'on', 'motivo': 'Resolución judicial ficticia'})
        self.assertEqual((self.vinculo.revocacion.autor, self.vinculo.revocacion.motivo),
                         (admin, 'Resolución judicial ficticia'))
        self.assertContains(self.client.get(reverse('apoderados_revision')), 'Resolución judicial ficticia')


class MayoriaDeEdadTests(TestCase):

    def setUp(self):
        self.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, self.madre.user, apoderado_id=self.madre.id_apoderado)

    def cumplir_18(self, alumno):
        User.objects.filter(pk=alumno.user_id).update(fecha_nacimiento=hace_anios(18))

    def entrar_como(self, alumno):
        entrar(self.client, User.objects.get(pk=alumno.user_id), alumno_id=alumno.id_alumno)

    def test_a_los_18_el_vinculo_deja_de_autorizar(self):
        vinculo = crear_menor_vinculado(self.madre)
        self.cumplir_18(vinculo.alumno)
        vinculo = Vinculo.objects.get(pk=vinculo.pk)
        self.assertFalse(vinculo.autoriza(vinculo.alumno))
        for nombre in ('apoderado_clases_estudiante', 'apoderado_clave_estudiante'):
            self.assertEqual(self.client.get(reverse(nombre, args=[vinculo.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('apoderado_comprar_paquete', args=[vinculo.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse('portal_apoderado')), 'cumplió 18 años')

    def test_la_cuenta_que_creo_el_apoderado_pide_una_clave_nueva_a_los_18(self):
        self.client.post(reverse('apoderado_registrar_estudiante'), datos_estudiante())
        alumno = Alumno.objects.get(user__rut=RUT_NINO)
        self.assertTrue(ClaveDelApoderado.objects.filter(user=alumno.user).exists())
        self.entrar_como(alumno)
        self.assertEqual(self.client.get(reverse('alumno_pag1')).status_code, 200)  # menor: sin cambio

        self.cumplir_18(alumno)
        self.assertRedirects(self.client.get(reverse('alumno_pag1')), reverse('nueva_clave_estudiante'))
        self.assertRedirects(self.client.post(reverse('nueva_clave_estudiante'), NUEVA), reverse('alumno_pag1'))
        self.assertFalse(ClaveDelApoderado.objects.filter(user=alumno.user).exists())
        self.assertEqual(self.client.get(reverse('alumno_pag1')).status_code, 200)  # sigue con su sesion
        self.assertTrue(User.objects.get(pk=alumno.user_id).check_password(NUEVA['new_password1']))

    def test_el_apoderado_que_cambia_la_clave_vuelve_a_marcarla(self):
        vinculo = crear_menor_vinculado(self.madre)
        self.client.post(reverse('apoderado_clave_estudiante', args=[vinculo.pk]), NUEVA)
        self.assertTrue(ClaveDelApoderado.objects.filter(user=vinculo.alumno.user).exists())

    def test_el_adolescente_que_eligio_su_clave_no_tiene_que_cambiarla(self):
        self.client.logout()
        self.client.post(reverse('adolescente_registro'), datos_adolescente())
        self.assertFalse(ClaveDelApoderado.objects.exists())
