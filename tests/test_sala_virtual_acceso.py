"""Sala virtual: solo entra una inscripcion confirmada de una sesion no cancelada.

'pendiente' solo la asigna un admin a mano y aun no esta confirmada; antes
mostraba "Unirse a la Clase" y la vista dejaba entrar con cualquier inscripcion,
incluso cancelada.
"""

from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Asignatura, Clase, Genero, Inscripcion, Profesor, SesionClase
from alumnos.views import nombre_sala_jitsi
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
RUT_ANA = '11111111-1'
CONFIRMADA, PENDIENTE, CANCELADA = (Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE,
                                    Inscripcion.ESTADO_CANCELADA)


class AccesoSalaVirtualTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ana = crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        profesor = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=time(10, 0), profesor=profesor)

    def inscribir(self, estado=CONFIRMADA, sesion_estado=SesionClase.ESTADO_PROGRAMADA, dias=2):
        sesion = crear_sesion(self.clase, dias=dias, estado=sesion_estado)
        return Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=sesion, estado=estado)

    def entrar(self):
        self.client.post(reverse('login'), {'username': RUT_ANA, 'password': CLAVE})
        return self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))

    def test_regla_puede_unirse(self):
        casos = [
            ('confirmada', dict(estado=CONFIRMADA), True),
            ('pendiente', dict(estado=PENDIENTE), False),
            ('cancelada por la alumna', dict(estado=CANCELADA), False),
            ('sesion cancelada', dict(sesion_estado=SesionClase.ESTADO_CANCELADA), False),
        ]
        for i, (nombre, datos, esperado) in enumerate(casos):
            with self.subTest(nombre):
                self.assertIs(self.inscribir(dias=i + 1, **datos).puede_unirse, esperado)

    def test_confirmada_sin_sesion_puntual_puede_unirse(self):
        insc = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, estado=CONFIRMADA)
        self.assertTrue(insc.puede_unirse)

    def test_confirmada_entra_a_la_sala(self):
        self.inscribir()
        self.assertEqual(self.entrar().status_code, 200)

    def test_sin_inscripcion_no_entra(self):
        self.assertEqual(self.entrar().status_code, 403)

    def test_pendiente_no_entra(self):
        self.inscribir(estado=PENDIENTE)
        self.assertEqual(self.entrar().status_code, 403)

    def test_cancelada_por_la_alumna_no_entra(self):
        self.inscribir(estado=CANCELADA)
        self.assertEqual(self.entrar().status_code, 403)

    def test_sesion_cancelada_no_entra(self):
        self.inscribir(sesion_estado=SesionClase.ESTADO_CANCELADA)
        self.assertEqual(self.entrar().status_code, 403)

    def test_basta_una_inscripcion_valida_de_la_clase(self):
        self.inscribir(sesion_estado=SesionClase.ESTADO_CANCELADA, dias=2)
        self.inscribir(estado=CONFIRMADA, dias=5)
        self.assertEqual(self.entrar().status_code, 200)


class MatrizAccesoSalaTests(TestCase):
    """SCRUM-87: quien entra a la sala virtual y quien inicia el directo.

    La regla se decide por la cuenta (request.user), no por las claves de sesion.
    Los casos de inscripcion (pendiente, cancelada, sesion cancelada) estan arriba;
    admin, staff y campo ``rol`` en tests.test_menores_prerrequisitos.
    """

    @classmethod
    def setUpTestData(cls):
        cls.ana = crear_alumno(RUT_ANA, 'Ana', Genero.objects.create(descripcion='Otro'))
        cls.titular = crear_profesor('20000000-1', 'profe@lbwus.cl', None)
        cls.otro = crear_profesor('30000000-2', 'otro@lbwus.cl', None)
        cls.sin_titulo = crear_profesor('40000000-3', 'pendiente@lbwus.cl', None,
                                        titulo_estado=Profesor.TITULO_EN_REVISION)
        asignatura = Asignatura.objects.create(nombre='Álgebra')
        cls.clase = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                         horario=time(10, 0), profesor=cls.titular)
        cls.clase_sin_titulo = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                                    horario=time(12, 0), profesor=cls.sin_titulo)

    def abrir(self, user, clase=None, **sesion_extra):
        self.client.force_login(user)
        sesion = self.client.session
        sesion.update(sesion_extra)
        sesion.save()
        return self.client.get(reverse('sala_virtual', args=[(clase or self.clase).id_clase]))

    def iniciar(self, profesor, clase=None):
        self.client.force_login(profesor.user)
        sesion = self.client.session
        sesion['profesor_id'] = profesor.id_profesor
        sesion.save()
        return self.client.post(reverse('iniciar_directo', args=[(clase or self.clase).id_clase]),
                                {'descripcion_vivo': 'Hoy', 'temas_vivo': 'Matrices'})

    def test_titular_habilitado_entra_y_ve_iniciar_directo(self):
        respuesta = self.abrir(self.titular.user, profesor_id=self.titular.id_profesor)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context['puede_iniciar'])
        self.assertContains(respuesta, 'id="btn-iniciar-directo"')
        self.assertContains(respuesta, 'const isProfesor = true;')

    def test_titular_sin_rol_profesor_activo_entra_pero_no_ve_iniciar(self):
        """Iniciar es un POST con @profesor_required_json: sin ese rol no se ofrece."""
        respuesta = self.abrir(self.titular.user)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context['puede_iniciar'])
        self.assertNotContains(respuesta, 'id="btn-iniciar-directo"')
        self.assertContains(respuesta, 'const isProfesor = false;')

    def test_titular_sin_titulo_aprobado_no_entra(self):
        respuesta = self.abrir(self.sin_titulo.user, self.clase_sin_titulo, profesor_id=self.sin_titulo.id_profesor)
        self.assertEqual(respuesta.status_code, 403)

    def test_otro_profesor_no_entra_aunque_tenga_titulo(self):
        self.assertEqual(self.abrir(self.otro.user, profesor_id=self.otro.id_profesor).status_code, 403)

    def test_la_clave_de_sesion_del_titular_no_basta(self):
        """Antes bastaba con session['profesor_id'] o session['alumno_id'] (regla 1)."""
        self.assertEqual(self.abrir(self.otro.user, profesor_id=self.titular.id_profesor).status_code, 403)
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, dias=2),
                                   estado=CONFIRMADA)
        self.assertEqual(self.abrir(self.otro.user, alumno_id=self.ana.id_alumno).status_code, 403)

    def test_alumna_confirmada_entra_sin_ver_iniciar_directo(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, dias=2),
                                   estado=CONFIRMADA)
        respuesta = self.abrir(self.ana.user, alumno_id=self.ana.id_alumno)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context['puede_iniciar'])
        self.assertNotContains(respuesta, 'id="btn-iniciar-directo"')

    def test_alumna_no_inscrita_no_entra(self):
        self.assertEqual(self.abrir(self.ana.user, alumno_id=self.ana.id_alumno).status_code, 403)

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)

    def test_cuenta_inactiva_va_al_login(self):
        self.client.force_login(self.titular.user)
        User.objects.filter(pk=self.titular.user.pk).update(is_active=False)
        respuesta = self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)

    def test_la_sala_jitsi_no_se_puede_adivinar(self):
        """meet.jit.si es publico: el nombre de la sala no puede salir del id de la clase."""
        respuesta = self.abrir(self.titular.user, profesor_id=self.titular.id_profesor)
        sala = respuesta.context['sala_jitsi']
        self.assertContains(respuesta, f"roomName: '{sala}'")
        self.assertNotContains(respuesta, f'lbwus-clase-privada-{self.clase.id_clase}')
        self.assertEqual(len(sala), len('lbwus-') + 32)
        self.assertNotEqual(sala, nombre_sala_jitsi(self.clase_sin_titulo))
        otra = self.abrir(self.sin_titulo.user, self.clase_sin_titulo)  # 403: no expone la sala
        self.assertNotIn(b'roomName', otra.content)

    def test_iniciar_directo_solo_el_titular_habilitado(self):
        self.assertTrue(self.iniciar(self.titular).json()['success'])
        self.clase.refresh_from_db()
        self.assertTrue(self.clase.en_vivo)

    def test_iniciar_directo_rechaza_otro_profesor_y_titular_sin_titulo(self):
        for nombre, profesor, clase in (('otro profesor', self.otro, self.clase),
                                        ('titular sin titulo', self.sin_titulo, self.clase_sin_titulo)):
            with self.subTest(nombre):
                respuesta = self.iniciar(profesor, clase)
                self.assertEqual(respuesta.status_code, 403)
                clase.refresh_from_db()
                self.assertFalse(clase.en_vivo)
