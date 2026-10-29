"""Formulario de contacto: el mensaje se guarda de verdad y el administrador lo ve.

Antes la pagina mostraba "Mensaje Enviado" sin mandar nada. Datos ficticios.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from admin_portal.models import MensajeContacto
from alumnos.models import Tutor
from alumnos.views import LIMITE_CONTACTO
from tests.test_apoderados import CLAVE, entrar

User = get_user_model()
URL = reverse('contactos')


def datos(**cambios):
    return {'nombre': 'Ana Ficticia', 'correo': 'ana@example.com', 'mensaje': '¿Tienen clases de física?', **cambios}


class EnvioTests(TestCase):

    def setUp(self):
        cache.clear()  # el tope por IP vive en la cache compartida

    def test_la_pagina_envia_los_campos_que_valida_el_servidor(self):
        respuesta = self.client.get(URL)
        for campo in ('name="nombre"', 'name="correo"', 'name="mensaje"', 'csrfmiddlewaretoken'):
            self.assertContains(respuesta, campo)

    def test_el_mensaje_se_guarda(self):
        respuesta = self.client.post(URL, datos())
        self.assertEqual(respuesta.json(), {'success': True})
        mensaje = MensajeContacto.objects.get()
        self.assertEqual((mensaje.nombre, mensaje.correo, mensaje.mensaje),
                         ('Ana Ficticia', 'ana@example.com', '¿Tienen clases de física?'))

    def test_datos_invalidos_no_se_guardan_y_se_explica_por_que_en_espanol(self):
        casos = (({'correo': 'no-es-correo'}, 'Por favor, ingresa un correo válido.'),
                 ({'nombre': ''}, 'Por favor, dinos tu nombre.'),
                 ({'mensaje': 'x' * 2001}, 'Tu mensaje puede tener hasta 2000 caracteres.'))
        for cambios, explicacion in casos:
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(URL, datos(**cambios))
                self.assertEqual(respuesta.status_code, 400)
                self.assertEqual(respuesta.json(), {'success': False, 'message': explicacion})
        self.assertFalse(MensajeContacto.objects.exists())

    def test_tope_de_mensajes_por_ip(self):
        for _ in range(LIMITE_CONTACTO):
            self.assertEqual(self.client.post(URL, datos()).status_code, 200)
        respuesta = self.client.post(URL, datos())
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(MensajeContacto.objects.count(), LIMITE_CONTACTO)
        otra_ip = self.client.post(URL, datos(), REMOTE_ADDR='10.0.0.2')
        self.assertEqual(otra_ip.status_code, 200)


class BandejaDelAdministradorTests(TestCase):

    def test_el_administrador_ve_los_mensajes_escapados(self):
        MensajeContacto.objects.create(nombre='<script>alert(1)</script>', correo='x@example.com', mensaje='Hola')
        admin = User.objects.create_user('10101010-1', password=CLAVE, rol='admin', first_name='Admin')
        entrar(self.client, admin, admin_id=Tutor.objects.create(user=admin).id_tutor)

        respuesta = self.client.get(reverse('contactos_adm'))

        self.assertContains(respuesta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(respuesta, '<script>alert(1)</script>')
        self.assertNotContains(respuesta, 'No hay mensajes de contacto aún')

    def test_un_anonimo_no_ve_los_mensajes(self):  # los demas roles: test_control_acceso
        MensajeContacto.objects.create(nombre='Ana Ficticia', correo='ana@example.com', mensaje='Hola')
        self.assertNotContains(self.client.get(reverse('contactos_adm')), 'ana@example.com', status_code=302)
