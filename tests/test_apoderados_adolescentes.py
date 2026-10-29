"""Fase 1b-ii de menores: el adolescente de 14 a 17 invita a su madre o padre.

Datos ficticios. El correo del apoderado solo entrega el enlace: la prueba del
vinculo sigue siendo la revision de identidad (1a) y del certificado (1b-i).
"""

import re
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.db.models import F
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, Genero, Tutor
from apoderados.forms import VERSION_DECLARACION_ADOLESCENTE, VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, Invitacion, SolicitudAdolescente, Vinculo
from apoderados.tokens import firmar_invitacion
from tests.test_apoderados import CLAVE, RUT, crear_apoderado, datos_registro, entrar, imagen
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
RUT_TEEN, RUT_OTRO_TEEN = '11111111-1', '22222222-2'
CORREO_TEEN, CORREO_MAMA = 'teen@demo.cl', 'mama@demo.cl'


def hace_anios(anios):
    return date(date.today().year - anios, 1, 1)


def datos_adolescente(**cambios):
    datos = {
        'nombre': 'Valentina Ficticia', 'rut': RUT_TEEN, 'correo': CORREO_TEEN,
        'fecha_nacimiento': hace_anios(15).isoformat(), 'nivel_educacion': 'media',
        'correo_apoderado': CORREO_MAMA, 'password': CLAVE, 'confirmar_password': CLAVE,
        'acepta_declaracion': 'on',
    }
    datos.update(cambios)
    return datos


def crear_adolescente(rut=RUT_TEEN, correo=CORREO_TEEN, confirmado=True):
    user = User.objects.create_user(rut, rut=rut, email=correo, password=CLAVE, first_name=f'Teen {rut}',
                                    fecha_nacimiento=hace_anios(15))
    alumno = Alumno.objects.create(user=user, nivel_educacion='media')
    return SolicitudAdolescente.objects.create(
        alumno=alumno, correo_apoderado=CORREO_MAMA, version_declaracion=VERSION_DECLARACION_ADOLESCENTE,
        declaracion_aceptada=timezone.now(), correo_confirmado=timezone.now() if confirmado else None)


def enlace(correo):
    return re.search(r'https?://\S+', correo.body).group(0).replace('http://testserver', '')


def url_invitacion(invitacion):
    return reverse('apoderado_invitacion', args=[firmar_invitacion(invitacion)])


class FlujoCompletoTests(TestCase):

    def test_del_registro_del_adolescente_al_vinculo_verificable(self):
        # 1. El adolescente se registra: aun no se invita a nadie.
        respuesta = self.client.post(reverse('adolescente_registro'), datos_adolescente())
        self.assertRedirects(respuesta, reverse('adolescente_solicitud'))
        solicitud = SolicitudAdolescente.objects.select_related('alumno__user').get()
        self.assertEqual((solicitud.alumno.user.rol, solicitud.correo_apoderado), ('alumno', CORREO_MAMA))
        self.assertEqual([m.to for m in mail.outbox], [[CORREO_TEEN]])
        self.assertFalse(Invitacion.objects.exists())

        # 2. Confirma su correo: recien ahi sale la invitacion, una sola vez.
        confirmacion = enlace(mail.outbox[0])
        self.client.get(confirmacion)
        self.assertEqual(self.client.get(confirmacion).status_code, 400)
        invitacion = Invitacion.objects.get()
        self.assertEqual([m.to for m in mail.outbox[1:]], [[CORREO_MAMA]])
        cuerpo = mail.outbox[1].body
        self.assertIn('Valentina Ficticia', cuerpo)
        self.assertNotIn(RUT_TEEN, cuerpo)  # minimizacion: sin RUT ni fecha de nacimiento
        self.assertNotIn(str(hace_anios(15).year), cuerpo)

        # 3. La madre abre el enlace sin cuenta: se guarda y se registra.
        self.client.logout()
        link = enlace(mail.outbox[1])
        self.assertContains(self.client.get(link), 'Valentina Ficticia te invitó a ser su apoderado')
        self.client.post(reverse('registro_apoderado'), datos_registro(correo=CORREO_MAMA))
        self.assertContains(self.client.get(reverse('portal_apoderado')), 'Tienes una invitación pendiente')

        # 4. Acepta (aun sin identidad verificada): vinculo pendiente, enlace usado.
        self.client.post(link, {'parentesco': 'madre', 'acepta_declaracion': 'on', 'documento': imagen()})
        vinculo = Vinculo.objects.get()
        self.assertEqual((vinculo.alumno, vinculo.estado, vinculo.version_declaracion),
                         (solicitud.alumno, Vinculo.PENDIENTE, VERSION_DECLARACION_VINCULO))
        invitacion.refresh_from_db()
        self.assertEqual(invitacion.vinculo, vinculo)
        self.assertEqual(self.client.get(link).status_code, 400)

        # 5. El admin solo lo ve cuando la identidad de la madre esta verificada.
        admin = User.objects.create_user('10101010-1', password=CLAVE, rol='admin', first_name='Admin')
        entrar(self.client, admin, admin_id=Tutor.objects.create(user=admin).id_tutor)
        self.assertContains(self.client.get(reverse('apoderados_revision')), 'Vínculos por verificar (0)')
        Apoderado.objects.update(estado=Apoderado.VERIFICADO)
        respuesta = self.client.get(reverse('apoderados_revision'))
        self.assertContains(respuesta, 'Vínculos por verificar (1)')
        self.assertContains(respuesta, f'El estudiante invitó a {CORREO_MAMA}')


class RegistroAdolescenteTests(TestCase):

    def test_validaciones_del_registro(self):
        casos = {
            'menor de 14': (dict(fecha_nacimiento=hace_anios(13).isoformat()), 'fecha_nacimiento'),
            'mayor de edad': (dict(fecha_nacimiento=hace_anios(18).isoformat()), 'fecha_nacimiento'),
            'sin correo propio': (dict(correo=''), 'correo'),
            'se invita a si mismo': (dict(correo_apoderado=CORREO_TEEN.upper()), 'correo_apoderado'),
            'sin declaracion': (dict(acepta_declaracion=''), 'acepta_declaracion'),
        }
        for nombre, (cambios, campo) in casos.items():
            with self.subTest(nombre):
                respuesta = self.client.post(reverse('adolescente_registro'), datos_adolescente(**cambios))
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertFalse(Alumno.objects.exists())

    def test_con_sesion_abierta_va_a_su_portal(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)
        self.assertRedirects(self.client.get(reverse('adolescente_registro')), reverse('portal_apoderado'))


class AceptarInvitacionTests(TestCase):

    def setUp(self):
        self.solicitud = crear_adolescente()
        self.invitacion = self.solicitud.invitar(CORREO_MAMA)
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def aceptar(self, invitacion=None, **datos):
        return self.client.post(url_invitacion(invitacion or self.invitacion),
                                {'parentesco': 'padre', 'acepta_declaracion': 'on', 'documento': imagen(), **datos})

    def test_enlaces_que_no_sirven(self):
        token = firmar_invitacion(self.invitacion)
        self.assertEqual(self.client.get(reverse('apoderado_invitacion', args=[token + 'x'])).status_code, 400)
        nueva = self.solicitud.invitar('papa@demo.cl')  # solo vale la ultima
        self.assertEqual(self.client.get(url_invitacion(self.invitacion)).status_code, 400)
        self.assertEqual(self.client.get(url_invitacion(nueva)).status_code, 200)
        # Se atrasan todas: el orden se mantiene y solo puede fallar por vencida.
        Invitacion.objects.update(enviada=F('enviada') - timedelta(days=8))
        self.assertEqual(self.client.get(url_invitacion(nueva)).status_code, 400)
        self.assertFalse(Vinculo.objects.exists())

    def test_aceptar_exige_declaracion_y_parentesco_del_certificado(self):
        self.aceptar(acepta_declaracion='')
        self.aceptar(parentesco='abuela')
        self.assertFalse(Vinculo.objects.exists())
        self.aceptar()
        self.assertEqual(Vinculo.objects.get().parentesco, 'padre')

    def test_apoderado_rechazado_no_acepta(self):
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.assertRedirects(self.aceptar(), reverse('portal_apoderado'))
        self.assertFalse(Vinculo.objects.exists())

    def test_no_duplica_un_vinculo_existente(self):
        self.aceptar()
        otra = self.solicitud.invitar(CORREO_MAMA)
        self.aceptar(otra)
        self.assertEqual(Vinculo.objects.count(), 1)

    def test_otra_cuenta_no_acepta(self):
        entrar(self.client, self.solicitud.alumno.user, alumno_id=self.solicitud.alumno.id_alumno)
        self.assertContains(self.client.get(url_invitacion(self.invitacion)), 'no es de apoderado')
        self.aceptar()
        self.assertFalse(Vinculo.objects.exists())

    def test_el_apoderado_no_maneja_la_clave_de_la_cuenta_del_adolescente(self):
        self.aceptar()
        vinculo = Vinculo.objects.get()
        Vinculo.objects.filter(pk=vinculo.pk).update(estado=Vinculo.VERIFICADO)
        self.assertNotContains(self.client.get(reverse('portal_apoderado')), 'Cambiar su contraseña')
        url = reverse('apoderado_clave_estudiante', args=[vinculo.pk])
        self.assertEqual(self.client.post(url, {'new_password1': 'Koala-Celeste-2026',
                                                'new_password2': 'Koala-Celeste-2026'}).status_code, 404)


class SolicitudDelAdolescenteTests(TestCase):

    def setUp(self):
        self.solicitud = crear_adolescente(confirmado=False)
        entrar(self.client, self.solicitud.alumno.user, alumno_id=self.solicitud.alumno.id_alumno)

    def invitar(self, correo='papa@demo.cl'):
        return self.client.post(reverse('adolescente_invitar'), {'correo_apoderado': correo})

    def test_sin_correo_confirmado_no_invita(self):
        self.invitar()
        self.assertFalse(Invitacion.objects.exists())

    def test_invita_a_otro_correo_con_limite_diario(self):
        SolicitudAdolescente.objects.update(correo_confirmado=timezone.now())
        self.invitar(CORREO_TEEN)  # no a si mismo
        self.assertFalse(Invitacion.objects.exists())
        for _ in range(Invitacion.LIMITE_DIARIO + 1):
            self.invitar()
        self.assertEqual(Invitacion.objects.count(), Invitacion.LIMITE_DIARIO)
        self.assertEqual(mail.outbox[0].to, ['papa@demo.cl'])
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.correo_apoderado, 'papa@demo.cl')

    def test_reenvio_de_confirmacion_limitado_a_uno_por_minuto(self):
        self.client.post(reverse('adolescente_reenviar_correo'))
        self.client.post(reverse('adolescente_reenviar_correo'))
        self.assertEqual(len(mail.outbox), 1)

    def test_el_portal_enlaza_la_solicitud(self):
        self.assertContains(self.client.get(reverse('alumno_pag1')), reverse('adolescente_solicitud'))

    def test_solo_el_adolescente_ve_su_solicitud(self):
        self.client.logout()
        respuesta = self.client.get(reverse('adolescente_solicitud'))
        self.assertRedirects(respuesta, reverse('login'), fetch_redirect_response=False)
        adulta = crear_alumno('33333333-3', 'Ana', Genero.objects.create(descripcion='Otro'))
        entrar(self.client, adulta.user, alumno_id=adulta.id_alumno)
        self.assertEqual(self.client.get(reverse('adolescente_solicitud')).status_code, 404)
