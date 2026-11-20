"""Campanita de notificaciones (paso B2a, decidido 02-nov). Datos ficticios."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notificaciones.models import LARGO_TEXTO, Notificacion, notificar
from alumnos.roles import ALUMNO, APODERADO, PROFESOR
from apoderados.models import Apoderado
from tests.test_apoderados import crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
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
    """La pagina es la misma para todos los roles; cada portal con base propia la muestra dentro de su marco.

    El docente y el alumno la ven dentro de su portal: su menu ya los lleva al panel, asi que no lleva 'Volver'.
    El apoderado sigue en el diseno publico y vuelve a su cuenta.
    """

    def test_el_apoderado_vuelve_a_su_cuenta_en_el_diseno_publico(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        entrar(self.client, apoderado, APODERADO)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertContains(r, f'class="notif-pagina__volver" href="{reverse("portal_apoderado")}"')
        self.assertContains(r, 'Volver a mi cuenta')
        self.assertNotContains(r, 'class="sidebar"')
        self.assertNotContains(r, 'class="sidebar-menu"')

    def test_el_alumno_la_ve_dentro_de_su_portal_sin_volver(self):
        notificar(self.ana.user, 'Tu profesor cancelo la clase')
        entrar(self.client, self.ana, ALUMNO)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertTemplateUsed(r, 'alumnos/base_alumno.html')
        self.assertContains(r, '<aside class="sidebar-menu"')  # el menu del portal del alumno
        self.assertContains(r, 'Tu profesor cancelo la clase')
        self.assertNotContains(r, 'notif-pagina__volver')
        self.assertEqual(r.content.decode().count('<main'), 1)

    def test_el_titulo_de_la_barra_del_alumno_es_el_de_la_pagina_y_no_se_repite(self):
        # Su barra superior cambia de titulo con cada vista: aqui debe decir Notificaciones, no Dashboard.
        entrar(self.client, self.ana, ALUMNO)
        html = self.client.get(reverse('mis_notificaciones')).content.decode()
        self.assertIn('<h1 id="portal-title">Notificaciones</h1>', html)
        self.assertEqual(html.count('<h1'), 1)  # sin el encabezado de la pagina publica, que lo duplicaria
        self.assertNotIn('notif-pagina__cabecera', html)

    def test_en_el_menu_del_alumno_no_queda_marcado_el_dashboard(self):
        entrar(self.client, self.ana, ALUMNO)
        html = self.client.get(reverse('mis_notificaciones')).content.decode()
        self.assertIn('data-view="view-dashboard"', html)
        self.assertNotIn('sidebar-view-btn active', html)

    def test_el_menor_no_ve_buzon_ni_soporte_tampoco_desde_notificaciones(self):
        apoderado = crear_apoderado('44444444-4', Apoderado.VERIFICADO)
        menor = crear_menor_vinculado(apoderado, rut='77777777-7').alumno
        entrar(self.client, menor, ALUMNO)
        html = self.client.get(reverse('mis_notificaciones')).content.decode()
        self.assertIn('data-view="view-progress"', html)
        self.assertNotIn('data-view="view-inbox"', html)
        self.assertNotIn('data-view="view-support"', html)

    def test_el_docente_conserva_el_titulo_de_su_barra_y_el_encabezado_de_la_pagina(self):
        entrar(self.client, self.profesor, PROFESOR)
        html = self.client.get(reverse('mis_notificaciones')).content.decode()
        self.assertIn('notif-pagina__cabecera', html)
        self.assertIn('<h1 id="notif-titulo">Notificaciones</h1>', html)
        self.assertNotIn('id="portal-title"', html)  # esa barra es del portal del alumno

    def test_el_docente_la_ve_dentro_de_su_portal_sin_volver(self):
        notificar(self.profesor.user, 'Te reservaron Algebra')
        entrar(self.client, self.profesor, PROFESOR)
        r = self.client.get(reverse('mis_notificaciones'))
        self.assertContains(r, 'class="sidebar"')  # el menu del portal docente
        self.assertContains(r, 'Te reservaron Algebra')
        self.assertNotContains(r, 'notif-pagina__volver')
        self.assertEqual(r.content.decode().count('<main'), 1)

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
