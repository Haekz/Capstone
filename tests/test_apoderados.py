"""Cuenta del apoderado y verificacion de su identidad.

Datos ficticios. Cubre registro (validaciones), confirmacion de correo (un solo
uso, vencimiento, manipulacion), revision de soporte (evidencia obligatoria) y
restricciones: una cuenta verificada no abre nada de alumnos, profesores ni admin.
"""

import io
import re
from datetime import date, datetime, time as hora, timedelta
from unittest import mock

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from alumnos.models import Asignatura, Clase, Genero
from apoderados.documentos import preparar
from apoderados.forms import VERSION_DECLARACION
from apoderados.models import Apoderado, Documento, RevisionIdentidad
from apoderados.tokens import token_correo
from apoderados.views import CLAVE_ENVIO
from soporte.models import AgenteSoporte, Habilitacion, Ticket
from soporte.tickets import abrir_ticket
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno

User = get_user_model()
CLAVE = 'Ornitorrinco-Lila-2026'
RUT = '12345678-5'
ENLACE = re.compile(r'https?://[^/\s]+(/apoderados/confirmar/\S+/)')


def imagen(nombre='documento.jpg', formato='JPEG', **info):
    """Foto ficticia de un documento, como la subiria el apoderado."""
    salida = io.BytesIO()
    Image.new('RGB', (120, 80), 'white').save(salida, formato, **info)
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=f'image/{formato.lower()}')


def adjuntar(tipo, **titular):
    """Documento ya subido y cifrado, como lo deja el formulario."""
    contenido, formato = preparar(imagen())
    return Documento.objects.create(tipo=tipo, contenido=contenido, formato=formato, **titular)


def datos_registro(**cambios):
    datos = {
        'nombre': 'Carla Ficticia', 'rut': RUT, 'correo': 'carla@demo.cl', 'telefono': '',
        'fecha_nacimiento': '1985-05-10', 'password': CLAVE, 'confirmar_password': CLAVE,
        'carnet_frente': imagen('frente.jpg'), 'carnet_reverso': imagen('reverso.jpg'),
        'acepta_declaracion': 'on',
    }
    datos.update(cambios)
    return datos


def crear_apoderado(rut, estado=Apoderado.CORREO_PENDIENTE):
    user = User.objects.create_user(rut, rut=rut, email=f'{rut}@demo.cl', password=CLAVE,
                                    rol='apoderado', first_name=f'Apoderado {rut}')
    return Apoderado.objects.create(
        user=user, estado=estado, version_declaracion=VERSION_DECLARACION,
        declaracion_aceptada=timezone.now(),
        correo_verificado=None if estado == Apoderado.CORREO_PENDIENTE else timezone.now(),
    )


def entrar(client, user, **sesion):
    client.force_login(user)
    s = client.session
    s.update(sesion)
    s.save()


def crear_agente(rut, *categorias, lider=False):
    """Cuenta de soporte que recibe tickets de ``categorias``."""
    user = User.objects.create_user(rut, rut=rut, email=f'{rut}@soporte.cl', password=CLAVE,
                                    rol='soporte', first_name=f'Agente {rut}')
    agente = AgenteSoporte.objects.create(user=user, es_lider=lider)
    Habilitacion.objects.bulk_create([Habilitacion(agente=agente, categoria=c) for c in categorias])
    return agente


def entrar_soporte(client, agente):
    entrar(client, agente.user, soporte_id=agente.id_agente)


class RegistroTests(TestCase):

    def test_registro_valido_crea_la_cuenta_pendiente_y_envia_el_enlace(self):
        respuesta = self.client.post(reverse('registro_apoderado'), datos_registro())

        self.assertRedirects(respuesta, reverse('portal_apoderado'))
        apoderado = Apoderado.objects.get(user__rut=RUT)
        self.assertEqual(apoderado.estado, Apoderado.CORREO_PENDIENTE)
        self.assertEqual(apoderado.user.rol, 'apoderado')
        self.assertEqual(apoderado.version_declaracion, VERSION_DECLARACION)
        self.assertIsNotNone(apoderado.declaracion_aceptada)
        self.assertTrue(apoderado.user.check_password(CLAVE))
        self.assertEqual(self.client.session['apoderado_id'], apoderado.id_apoderado)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['carla@demo.cl'])
        self.assertRegex(mail.outbox[0].body, ENLACE)

    def test_validaciones_del_registro(self):
        User.objects.create_user('11111111-1', rut='11111111-1', email='usado@demo.cl', password=CLAVE)
        menor = date(date.today().year - 17, 1, 1).isoformat()
        casos = {
            'menor de edad': (dict(fecha_nacimiento=menor), 'fecha_nacimiento'),
            'RUT invalido': (dict(rut='12345678-9'), 'rut'),
            'sin aceptar la declaracion': (dict(acepta_declaracion=''), 'acepta_declaracion'),
            'clave debil': (dict(password='12345678', confirmar_password='12345678'), 'password'),
            'claves distintas': (dict(confirmar_password='Otra-Clave-2026'), 'confirmar_password'),
            'RUT ya registrado': (dict(rut='11111111-1'), '__all__'),
            'correo ya registrado': (dict(correo='usado@demo.cl'), '__all__'),
        }
        for nombre, (cambios, campo) in casos.items():
            with self.subTest(nombre):
                respuesta = self.client.post(reverse('registro_apoderado'), datos_registro(**cambios))
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn(campo, respuesta.context['form'].errors)
        self.assertFalse(Apoderado.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_correo_falla_la_cuenta_queda_creada_y_se_avisa(self):
        with mock.patch('apoderados.correo.send_mail', side_effect=OSError('sin servidor')):
            respuesta = self.client.post(reverse('registro_apoderado'), datos_registro(), follow=True)
        self.assertTrue(Apoderado.objects.filter(user__rut=RUT).exists())
        self.assertContains(respuesta, 'No pudimos enviar el correo de confirmación')

    def test_con_sesion_de_otro_rol_no_se_muestra_el_registro(self):
        alumno = crear_alumno('11111111-1', 'Ana', Genero.objects.create(descripcion='Otro'))
        entrar(self.client, alumno.user, alumno_id=alumno.id_alumno)
        self.assertRedirects(self.client.get(reverse('registro_apoderado')), reverse('alumno_pag1'),
                             fetch_redirect_response=False)


class ConfirmacionCorreoTests(TestCase):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT)

    def enlace(self, apoderado=None, token=None):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        user = (apoderado or self.apoderado).user
        return reverse('apoderado_confirmar_correo', args=[
            urlsafe_base64_encode(force_bytes(user.pk)), token or token_correo.make_token(user)])

    def test_el_enlace_confirma_el_correo_y_sirve_una_sola_vez(self):
        enlace = self.enlace()
        self.client.get(enlace)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)
        self.assertIsNotNone(self.apoderado.correo_verificado)

        segunda = self.client.get(enlace)
        self.assertEqual(segunda.status_code, 400)
        self.assertTemplateUsed(segunda, 'apoderados/enlace_invalido.html')

    def test_enlaces_manipulados_no_confirman_nada(self):
        otro = crear_apoderado('11111111-1')
        casos = {
            'token alterado': self.enlace(token='abc-123456'),
            'uid que no es numero': reverse('apoderado_confirmar_correo', args=['YWJj', 'x-y']),
            'uid basura': reverse('apoderado_confirmar_correo', args=['%%%', 'x-y']),
            'token de otra cuenta': self.enlace(token=token_correo.make_token(otro.user)),
        }
        for nombre, enlace in casos.items():
            with self.subTest(nombre):
                self.assertEqual(self.client.get(enlace).status_code, 400)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.CORREO_PENDIENTE)

    def test_el_enlace_vence(self):
        enlace = self.enlace()
        despues = datetime.now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)
        with mock.patch.object(token_correo, '_now', return_value=despues):
            self.assertEqual(self.client.get(enlace).status_code, 400)
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.CORREO_PENDIENTE)

    def test_reenviar_respeta_la_espera_y_el_estado(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        url = reverse('apoderado_reenviar_correo')

        self.client.post(url)
        self.assertEqual(len(mail.outbox), 1)
        self.client.post(url)  # antes del minuto: no envia otro
        self.assertEqual(len(mail.outbox), 1)

        s = self.client.session
        s[CLAVE_ENVIO] = 0
        s.save()
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 2)

        self.apoderado.confirmar_correo()
        s = self.client.session
        s[CLAVE_ENVIO] = 0
        s.save()
        self.client.post(url)  # ya confirmado: no envia
        self.assertEqual(len(mail.outbox), 2)


class RevisionIdentidadTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.revisor = crear_agente('10101010-1', Ticket.APODERADOS, lider=True)

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.REVISION_PENDIENTE)
        for tipo in Documento.CARNET:
            adjuntar(tipo, apoderado=self.apoderado)
        abrir_ticket(Ticket.APODERADOS, apoderado=self.apoderado)
        entrar_soporte(self.client, self.revisor)

    def revisar(self, apoderado=None, **datos):
        return self.client.post(reverse('apoderado_revisar', args=[(apoderado or self.apoderado).pk]), datos)

    def test_aprobar_registra_la_evidencia(self):
        self.revisar(decision='aprobar', rut_coincide='on')
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.VERIFICADO)
        revision = self.apoderado.revisiones.get()
        self.assertEqual((revision.administrador, revision.documento, revision.canal, revision.rut_coincide),
                         (self.revisor.user, 'cedula', 'documento', True))

    def test_aprobar_exige_rut_coincidente(self):
        self.revisar(decision='aprobar')
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)
        self.assertFalse(RevisionIdentidad.objects.exists())

    def test_rechazar_exige_motivo_y_el_apoderado_lo_ve(self):
        self.revisar(decision='rechazar')
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.REVISION_PENDIENTE)

        self.revisar(decision='rechazar', observacion='El RUT no coincide con la cédula.')
        self.apoderado.refresh_from_db()
        self.assertEqual(self.apoderado.estado, Apoderado.RECHAZADO)

        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.assertContains(self.client.get(reverse('portal_apoderado')), 'El RUT no coincide con la cédula.')

    def test_solo_se_revisa_a_quien_confirmo_su_correo_y_no_tiene_decision(self):
        for estado in (Apoderado.CORREO_PENDIENTE, Apoderado.VERIFICADO, Apoderado.RECHAZADO):
            with self.subTest(estado=estado):
                otro = crear_apoderado(f'2{len(estado):07d}-0', estado)
                respuesta = self.revisar(otro, decision='aprobar', documento='cedula',
                                         canal='presencial', rut_coincide='on')
                self.assertEqual(respuesta.status_code, 404)
                otro.refresh_from_db()
                self.assertEqual(otro.estado, estado)

    def test_la_bandeja_muestra_pendientes_y_el_registro(self):
        respuesta = self.client.get(reverse('apoderados_revision'))
        self.assertContains(respuesta, RUT)
        self.assertContains(respuesta, 'Registro de decisiones')


class RestriccionesDeAccesoTests(TestCase):
    """Una cuenta de apoderado, incluso verificada, no abre nada mas."""

    @classmethod
    def setUpTestData(cls):
        cls.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        profesor = crear_profesor('20000000-1', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', horario=hora(10, 0), profesor=profesor)
        crear_sesion(cls.clase, dias=2)
        cls.alumno = crear_alumno('11111111-1', 'Ana', Genero.objects.create(descripcion='Otro'))

    def test_login_lleva_al_portal_del_apoderado(self):
        respuesta = self.client.post(reverse('login'), {'username': RUT, 'password': CLAVE})
        self.assertRedirects(respuesta, reverse('portal_apoderado'))
        self.assertEqual(self.client.session['apoderado_id'], self.apoderado.id_apoderado)
        menu = self.client.get(reverse('portal_apoderado')).context['usuario_sesion']
        self.assertEqual((menu['rol'], menu['texto_panel']), ('Apoderado', 'Mi cuenta'))

    def test_verificado_no_entra_a_portales_de_otros_roles(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        for vista in ('alumno_pag1', 'panel_profesor', 'dashboard_admin', 'crud',
                      'resenas_moderacion', 'apoderados_revision'):
            with self.subTest(vista=vista):
                self.assertRedirects(self.client.get(reverse(vista)), reverse('portal_apoderado'))

    def test_verificado_no_entra_a_la_sala_virtual(self):
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        respuesta = self.client.get(reverse('sala_virtual', args=[self.clase.id_clase]))
        self.assertEqual(respuesta.status_code, 403)

    def test_verificado_no_puede_revisar_apoderados(self):
        pendiente = crear_apoderado('22222222-2', Apoderado.REVISION_PENDIENTE)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        self.client.post(reverse('apoderado_revisar', args=[pendiente.pk]),
                         dict(decision='aprobar', documento='cedula', canal='presencial', rut_coincide='on'))
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, Apoderado.REVISION_PENDIENTE)

    def test_el_portal_es_solo_del_apoderado(self):
        self.assertRedirects(self.client.get(reverse('portal_apoderado')), reverse('login'),
                             fetch_redirect_response=False)
        entrar(self.client, self.alumno.user, alumno_id=self.alumno.id_alumno)
        self.assertRedirects(self.client.get(reverse('portal_apoderado')), reverse('alumno_pag1'),
                             fetch_redirect_response=False)
        self.client.post(reverse('apoderado_reenviar_correo'))
        self.assertEqual(len(mail.outbox), 0)


class MinimizacionDeDatosTests(TestCase):

    def test_la_app_no_guarda_archivos_en_disco_ni_direcciones_ip(self):
        prohibidos = (models.FileField, models.GenericIPAddressField)
        for modelo in apps.get_app_config('apoderados').get_models():
            for campo in modelo._meta.get_fields():
                with self.subTest(campo=f'{modelo.__name__}.{campo.name}'):
                    self.assertNotIsInstance(campo, prohibidos)

    def test_los_documentos_solo_se_guardan_en_documento_contenido(self):
        # El unico binario es el documento cifrado, que se borra al decidir.
        binarios = [f'{modelo.__name__}.{campo.name}'
                    for modelo in apps.get_app_config('apoderados').get_models()
                    for campo in modelo._meta.get_fields() if isinstance(campo, models.BinaryField)]
        self.assertEqual(binarios, ['Documento.contenido'])
