"""El apoderado registra al estudiante y se verifica el vinculo.

Datos ficticios. Cubre registro del menor (validaciones), revision del vinculo
(evidencia obligatoria), cambio de contrasena por el apoderado y los bloqueos:
un menor, aun con vinculo verificado y un paquete pagado, no reserva, no compra
ni entra a clases hasta la contratacion por el apoderado.
"""

from datetime import date, time as hora
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, Asignatura, Clase, Genero, Inscripcion, PaqueteClases
from alumnos.services import MENSAJE_MENOR
from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, Documento, RevisionVinculo, Vinculo
from soporte.models import Ticket
from tests.test_apoderados import CLAVE, RUT, adjuntar, crear_agente, crear_apoderado, entrar, entrar_soporte, imagen
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import dar_paquete
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
CLAVE_NINO = 'Jirafa-Naranja-2026'
RUT_NINO, RUT_HERMANA = '11111111-1', '22222222-2'


def hace_anios(anios):
    return date(date.today().year - anios, 1, 1)


def datos_estudiante(**cambios):
    datos = {
        'nombre': 'Tomás Ficticio', 'rut': RUT_NINO, 'fecha_nacimiento': hace_anios(10).isoformat(),
        'nivel_educacion': 'basica', 'parentesco': 'madre', 'correo': '',
        'password': CLAVE_NINO, 'confirmar_password': CLAVE_NINO, 'documento': imagen('certificado.jpg'),
        'acepta_declaracion': 'on',
    }
    datos.update(cambios)
    return datos


def crear_menor_vinculado(apoderado, rut=RUT_NINO, estado=Vinculo.VERIFICADO):
    user = User.objects.create_user(rut, rut=rut, password=CLAVE_NINO, first_name=f'Menor {rut}',
                                    fecha_nacimiento=hace_anios(10))
    alumno = Alumno.objects.create(user=user, nivel_educacion='basica')
    return Vinculo.objects.create(apoderado=apoderado, alumno=alumno, parentesco='madre', estado=estado,
                                  version_declaracion=VERSION_DECLARACION_VINCULO,
                                  declaracion_aceptada=timezone.now())


class RegistroEstudianteTests(TestCase):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def registrar(self, **cambios):
        return self.client.post(reverse('apoderado_registrar_estudiante'), datos_estudiante(**cambios))

    def test_el_estudiante_queda_con_vinculo_pendiente_y_entra_con_su_rut(self):
        self.assertRedirects(self.registrar(), reverse('portal_apoderado'))
        vinculo = Vinculo.objects.select_related('alumno__user').get()
        self.assertEqual((vinculo.apoderado, vinculo.estado, vinculo.parentesco),
                         (self.apoderado, Vinculo.PENDIENTE, 'madre'))
        self.assertEqual(vinculo.version_declaracion, VERSION_DECLARACION_VINCULO)
        self.assertEqual((vinculo.alumno.user.rol, vinculo.alumno.user.email), ('alumno', ''))
        self.assertEqual(self.client.session['apoderado_id'], self.apoderado.id_apoderado)

        self.client.logout()
        respuesta = self.client.post(reverse('login'), {'username': RUT_NINO, 'password': CLAVE_NINO})
        self.assertRedirects(respuesta, reverse('alumno_pag1'))

    def test_dos_hermanos_sin_correo_propio(self):
        self.registrar()
        self.registrar(rut=RUT_HERMANA, nombre='Sofía Ficticia')
        self.assertEqual(self.apoderado.vinculos.count(), 2)

    def test_validaciones_del_registro(self):
        casos = {
            'menor de 6': (dict(fecha_nacimiento=hace_anios(5).isoformat()), 'fecha_nacimiento'),
            'mayor de edad': (dict(fecha_nacimiento=hace_anios(18).isoformat()), 'fecha_nacimiento'),
            'fecha futura': (dict(fecha_nacimiento=date(date.today().year + 1, 1, 1).isoformat()), 'fecha_nacimiento'),
            'RUT invalido': (dict(rut='12345678-9'), 'rut'),
            'RUT ya registrado': (dict(rut=RUT), '__all__'),
            'sin declaracion': (dict(acepta_declaracion=''), 'acepta_declaracion'),
            'parentesco sin certificado': (dict(parentesco='abuela'), 'parentesco'),
            'clave debil': (dict(password='12345678', confirmar_password='12345678'), 'password'),
        }
        for nombre, (cambios, campo) in casos.items():
            with self.subTest(nombre):
                respuesta = self.registrar(**cambios)
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertFalse(Vinculo.objects.exists())

    def test_solo_un_apoderado_verificado_registra_estudiantes(self):
        for estado in (Apoderado.CORREO_PENDIENTE, Apoderado.REVISION_PENDIENTE, Apoderado.RECHAZADO):
            with self.subTest(estado=estado):
                Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=estado)
                self.assertRedirects(self.registrar(), reverse('portal_apoderado'))
        self.assertFalse(Alumno.objects.exists())

    def test_otros_roles_no_registran_estudiantes(self):
        self.client.logout()
        self.assertRedirects(self.registrar(), reverse('login'), fetch_redirect_response=False)
        ana = crear_alumno('33333333-3', 'Ana', Genero.objects.create(descripcion='Otro'))
        entrar(self.client, ana.user, alumno_id=ana.id_alumno)
        self.assertRedirects(self.registrar(), reverse('alumno_pag1'), fetch_redirect_response=False)
        self.assertFalse(Vinculo.objects.exists())


class RevisionVinculoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.revisor = crear_agente('10101010-1', Ticket.APODERADOS)

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.PENDIENTE)
        adjuntar(Documento.CERTIFICADO, vinculo=self.vinculo)
        self.vinculo.abrir_ticket_si_revisable()
        entrar_soporte(self.client, self.revisor)

    def revisar(self, vinculo=None, **datos):
        return self.client.post(reverse('apoderado_revisar_vinculo', args=[(vinculo or self.vinculo).pk]), datos)

    def test_verificar_exige_documento_coincidente(self):
        self.revisar(decision='aprobar')
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.PENDIENTE)

        self.revisar(decision='aprobar', certificado_coincide='on')
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.VERIFICADO)
        revision = RevisionVinculo.objects.get()
        self.assertEqual((revision.administrador, revision.canal, revision.certificado_coincide),
                         (self.revisor.user, 'documento', True))

    def test_rechazar_exige_motivo_y_el_apoderado_lo_ve(self):
        self.revisar(decision='rechazar')
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.PENDIENTE)

        self.revisar(decision='rechazar', observacion='El certificado no corresponde al estudiante.')
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.RECHAZADO)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.assertContains(self.client.get(reverse('portal_apoderado')), 'El certificado no corresponde al estudiante.')

    def test_solo_vinculos_pendientes_de_apoderados_verificados(self):
        completos = dict(decision='aprobar', canal='presencial', certificado_coincide='on')
        for estado in (Vinculo.VERIFICADO, Vinculo.RECHAZADO):
            with self.subTest(vinculo=estado):
                Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=estado)
                self.assertEqual(self.revisar(**completos).status_code, 404)
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.PENDIENTE)
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.assertEqual(self.revisar(**completos).status_code, 404)

    def test_un_apoderado_no_verifica_vinculos(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.revisar(decision='aprobar', canal='presencial', certificado_coincide='on')
        self.vinculo.refresh_from_db()
        self.assertEqual(self.vinculo.estado, Vinculo.PENDIENTE)

    def test_la_bandeja_muestra_el_vinculo_pendiente(self):
        respuesta = self.client.get(reverse('apoderados_revision'))
        self.assertContains(respuesta, 'Vínculos por verificar (1)')
        self.assertContains(respuesta, RUT_NINO)


class BloqueosDelMenorTests(TestCase):
    """El caso mas favorable: vinculo verificado y paquete pagado. Igual no puede."""

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=hora(10, 0), profesor=cls.profesor)
        cls.sesion, cls.otra_sesion = crear_sesion(cls.clase, dias=2), crear_sesion(cls.clase, dias=3)
        cls.menor = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO)).alumno
        dar_paquete(cls.menor, cls.profesor)
        cls.adulta = crear_alumno('33333333-3', 'Ana', Genero.objects.create(descripcion='Otro'))
        dar_paquete(cls.adulta, cls.profesor)

    def entrar_como(self, alumno):
        entrar(self.client, alumno.user, alumno_id=alumno.id_alumno)

    def reservar(self):
        return self.client.post(reverse('reservar_sesion'), {'id_sesion': self.sesion.pk}).json()

    def test_la_adulta_si_reserva(self):
        self.entrar_como(self.adulta)
        self.assertTrue(self.reservar()['success'])

    def test_el_menor_no_reserva_ni_se_inscribe(self):
        self.entrar_como(self.menor)
        self.assertEqual(self.reservar(), {'success': False, 'message': MENSAJE_MENOR})
        respuesta = self.client.post(reverse('inscribir_clase'), {'id_clase': self.clase.id_clase}).json()
        self.assertEqual((respuesta['success'], respuesta['message']), (False, MENSAJE_MENOR))
        self.assertFalse(Inscripcion.objects.filter(alumno=self.menor).exists())

    def test_el_menor_no_reprograma(self):
        reserva = Inscripcion.objects.create(alumno=self.menor, clase=self.clase, sesion=self.sesion,
                                             paquete=PaqueteClases.objects.get(alumno=self.menor),
                                             estado=Inscripcion.ESTADO_CONFIRMADA)
        self.entrar_como(self.menor)
        url = reverse('reprogramar_inscripcion', args=[reserva.pk])
        self.assertFalse(self.client.post(url, {'id_sesion': self.otra_sesion.pk}).json()['success'])
        reserva.refresh_from_db()
        self.assertEqual(reserva.sesion, self.sesion)

    @mock.patch('alumnos.views._tx')
    def test_el_menor_no_compra(self, tx):
        self.entrar_como(self.menor)
        respuesta = self.client.post(reverse('comprar_paquete'),
                                     {'plan': 'progreso', 'profesor': self.profesor.id_profesor})
        self.assertRedirects(respuesta, reverse('alumno_pag1'), fetch_redirect_response=False)
        tx.assert_not_called()
        self.assertEqual(PaqueteClases.objects.filter(alumno=self.menor).count(), 1)

    def test_el_menor_no_entra_a_la_sala_aunque_tenga_inscripcion(self):
        Inscripcion.objects.create(alumno=self.menor, clase=self.clase, sesion=self.sesion,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        self.entrar_como(self.menor)
        self.assertEqual(self.client.get(reverse('sala_virtual', args=[self.clase.id_clase])).status_code, 403)

    def test_el_portal_del_menor_avisa_y_oculta_la_mensajeria(self):
        self.entrar_como(self.menor)
        respuesta = self.client.get(reverse('alumno_pag1'))
        self.assertContains(respuesta, 'Cuenta de estudiante menor de edad.')
        self.assertNotContains(respuesta, 'data-view="view-inbox"')

        self.entrar_como(self.adulta)
        self.assertContains(self.client.get(reverse('alumno_pag1')), 'data-view="view-inbox"')


class ClaveEstudianteTests(TestCase):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, estado=Vinculo.PENDIENTE)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def cambiar(self, vinculo=None):
        nueva = 'Koala-Celeste-2026'
        return self.client.post(reverse('apoderado_clave_estudiante', args=[(vinculo or self.vinculo).pk]),
                                {'new_password1': nueva, 'new_password2': nueva})

    def test_el_apoderado_cambia_la_clave_de_su_estudiante(self):
        self.assertRedirects(self.cambiar(), reverse('portal_apoderado'))
        self.assertTrue(User.objects.get(pk=self.vinculo.alumno.user_id).check_password('Koala-Celeste-2026'))

    def test_no_cambia_la_de_un_vinculo_ajeno_o_rechazado(self):
        ajeno = crear_menor_vinculado(crear_apoderado('55555555-5', Apoderado.VERIFICADO), rut=RUT_HERMANA)
        self.assertEqual(self.cambiar(ajeno).status_code, 404)
        Vinculo.objects.filter(pk=self.vinculo.pk).update(estado=Vinculo.RECHAZADO)
        self.assertEqual(self.cambiar().status_code, 404)
        self.assertTrue(User.objects.get(pk=self.vinculo.alumno.user_id).check_password(CLAVE_NINO))
