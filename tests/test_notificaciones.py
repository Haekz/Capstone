"""Campanita de notificaciones (paso B2a, decidido 02-nov). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notificaciones.models import LARGO_TEXTO, Notificacion, notificar
from alumnos.roles import ALUMNO, APODERADO, PROFESOR
from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado
from tests.test_paquetes import RUT_ANA, Escenario
from tests.test_resenas import BaseResenas, entrar

User = get_user_model()
ETIQUETA_NUEVA = 'class="notif-item__etiqueta"'


def crear_usuario(rut):
    return User.objects.create_user(rut, password='Clave-de-prueba-1', rut=rut, rol='profesor')


class NotificacionesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profe = crear_usuario('11111111-1')
        cls.otro = crear_usuario('22222222-2')

    def test_notificar_recorta_el_texto_al_largo_maximo(self):
        n = notificar(self.profe, 'x' * (LARGO_TEXTO + 50))
        self.assertEqual(len(n.texto), LARGO_TEXTO)
        self.assertFalse(n.leida)

    def test_la_pagina_exige_sesion(self):
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertEqual(r.status_code, 302)

    def test_cada_uno_ve_solo_las_suyas(self):
        notificar(self.profe, 'Te reservaron Algebra')
        notificar(self.otro, 'Aviso privado de otra persona')
        self.client.force_login(self.profe)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertContains(r, 'Te reservaron Algebra')
        self.assertNotContains(r, 'Aviso privado de otra persona')

    def test_al_abrirlas_quedan_leidas_pero_se_ven_como_nuevas_esa_vez(self):
        notificar(self.profe, 'Te reservaron Algebra')
        self.client.force_login(self.profe)
        self.assertContains(self.client.get(reverse('mis_notificaciones')), ETIQUETA_NUEVA)
        self.assertFalse(Notificacion.objects.filter(leida=False).exists())
        self.assertNotContains(self.client.get(reverse('mis_notificaciones')), ETIQUETA_NUEVA)

    def test_abrirlas_no_marca_las_de_otro(self):
        notificar(self.otro, 'Aviso de otra persona')
        self.client.force_login(self.profe)
        self.client.get(reverse('mis_notificaciones'))
        self.assertTrue(Notificacion.objects.filter(usuario=self.otro, leida=False).exists())

    def test_el_menu_muestra_el_contador_de_sin_leer(self):
        notificar(self.profe, 'Uno')
        notificar(self.profe, 'Dos')
        self.client.force_login(self.profe)
        r = self.client.get(reverse('home'))
        self.assertContains(r, 'class="notif-contador" aria-hidden="true">2</span>')
        self.assertContains(r, 'Notificaciones: 2 sin leer')

    def test_sin_sesion_no_hay_campanita(self):
        self.assertNotContains(self.client.get(reverse('home')), 'notif-btn')


class CampanitaDelAlumnoTests(Escenario):
    """El panel del alumno tiene su propio encabezado: alli tambien va la campanita (paso A3a)."""

    def test_el_panel_del_alumno_muestra_la_campanita_con_su_contador(self):
        notificar(self.ana.user, 'Tu profesor cancelo la clase')
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, 'class="btn-theme-toggle notif-btn"')
        self.assertContains(r, 'Notificaciones: 1 sin leer')
        self.assertContains(r, 'notificaciones/campanita.css')


class PaginaDeNotificacionesTests(BaseResenas):
    """La pagina es la misma para todos los roles: cada uno vuelve a su portal y lo vacio se explica."""

    def test_cada_rol_vuelve_a_su_propio_portal(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        casos = (
            (self.ana, ALUMNO, 'alumno_pag1', 'Volver a mi portal'),
            (self.profesor, PROFESOR, 'panel_profesor', 'Volver a mi panel'),
            (apoderado, APODERADO, 'portal_apoderado', 'Volver a mi cuenta'),
        )
        for perfil, rol, ruta, texto in casos:
            with self.subTest(rol=rol.clave):
                entrar(self.client, perfil, rol)
                r = self.client.get(reverse('mis_notificaciones'))
                self.assertContains(r, f'class="notif-pagina__volver" href="{reverse(ruta)}"')
                self.assertContains(r, texto)

    def test_sin_notificaciones_explica_que_apareceran_aqui(self):
        entrar(self.client, self.ana, ALUMNO)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertContains(r, 'No tienes notificaciones')
        self.assertContains(r, 'Aquí aparecerán los avisos')
        self.assertNotContains(r, 'class="notif-lista"')

    def test_con_notificaciones_no_se_muestra_el_estado_vacio(self):
        notificar(self.ana.user, 'Tu profesor cancelo la clase')
        entrar(self.client, self.ana, ALUMNO)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertContains(r, 'Tu profesor cancelo la clase')
        self.assertNotContains(r, 'No tienes notificaciones')
