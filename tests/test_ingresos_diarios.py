"""H8: personas distintas que inician sesion cada dia, sin guardar quien (admin_portal/ingresos.py)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from admin_portal.ingresos import de_hoy
from admin_portal.models import IngresoDiario
from tests.test_retiros import crear_admin, entrar_admin

User = get_user_model()


class IngresosDiariosTests(TestCase):

    def usuario(self, rut, rol='alumno'):
        return User.objects.create_user(rut, rut=rut, password='Clave-Segura-2026', rol=rol)

    def entrar(self, user):
        Client().force_login(user)  # login() de Django: dispara user_logged_in, como el formulario y Google

    def personas(self, rol, fecha=None):
        return IngresoDiario.objects.get(fecha=fecha or timezone.localdate(), rol=rol).personas

    def test_la_misma_persona_cuenta_una_vez_al_dia(self):
        ana = self.usuario('11111111-1')
        self.entrar(ana)
        self.entrar(ana)
        self.assertEqual(self.personas('alumno'), 1)

    def test_cuenta_personas_distintas_por_rol(self):
        self.entrar(self.usuario('11111111-1'))
        self.entrar(self.usuario('22222222-2'))
        self.entrar(self.usuario('33333333-3', rol='profesor'))
        self.assertEqual(self.personas('alumno'), 2)
        self.assertEqual(self.personas('profesor'), 1)
        self.assertEqual(de_hoy(), {'total': 3, 'por_rol': [('Alumno', 2), ('Profesor', 1)]})

    def test_quien_entro_ayer_no_cuenta_hoy(self):
        User.objects.filter(pk=self.usuario('22222222-2').pk).update(last_login=timezone.now() - timedelta(days=1))
        self.entrar(self.usuario('11111111-1'))
        self.assertEqual(self.personas('alumno'), 1)

    def test_los_dias_pasados_no_cambian(self):
        ayer = timezone.localdate() - timedelta(days=1)
        IngresoDiario.objects.create(fecha=ayer, rol='alumno', personas=5)
        self.entrar(self.usuario('11111111-1'))
        self.assertEqual(self.personas('alumno', ayer), 5)

    def test_no_guarda_quien_entro(self):
        self.assertEqual({campo.name for campo in IngresoDiario._meta.get_fields()}, {'id', 'fecha', 'rol', 'personas'})

    def test_sin_ingresos(self):
        self.assertEqual(de_hoy(), {'total': 0, 'por_rol': []})

    def test_el_panel_muestra_las_personas_de_hoy(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)  # el admin tambien inicia sesion: cuenta
        respuesta = self.client.get(reverse('dashboard_admin'))
        self.assertContains(respuesta, 'Personas que entraron hoy')
        self.assertContains(respuesta, 'Administrador: 1')
