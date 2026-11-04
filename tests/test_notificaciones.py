"""Campanita de notificaciones (paso B2a, decidido 02-nov). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notificaciones.models import LARGO_TEXTO, Notificacion, notificar
from tests.test_paquetes import RUT_ANA, Escenario

User = get_user_model()


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
        self.assertContains(self.client.get(reverse('mis_notificaciones')), 'Nueva:')
        self.assertFalse(Notificacion.objects.filter(leida=False).exists())
        self.assertNotContains(self.client.get(reverse('mis_notificaciones')), 'Nueva:')

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
