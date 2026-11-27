"""Admin: un solo "Usuarios" (21-nov). Antes habia dos listados de alumnos, el del dashboard (#usuarios) y /crud/ con el
diseno viejo, y el menu llevaba a uno u otro segun la pagina. Ahora /crud/ solo redirige (la ruta se mantiene para no
romper enlaces guardados) y "Eliminar" termina en el dashboard con su aviso. Datos ficticios.
"""

from django.contrib.auth import get_user_model
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from alumnos.models import Alumno, Genero
from tests.test_retiros import crear_admin, entrar_admin

USUARIOS = reverse('dashboard_admin') + '#usuarios'


class UnSoloUsuariosTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        Genero.objects.create(descripcion='Otro')
        cls.admin, cls.tutor = crear_admin()
        user = get_user_model().objects.create_user(username='30303030-3', rut='30303030-3', password='Clave-Prueba-1',
                                                    first_name='Beto')
        cls.alumno = Alumno.objects.create(user=user, nivel_educacion='media')

    def entrar(self):
        entrar_admin(self.client, self.admin, self.tutor)

    def test_la_ruta_antigua_lleva_a_usuarios_del_dashboard(self):
        self.entrar()
        for ruta in ('crud', 'reporte_alumnos'):
            with self.subTest(ruta=ruta):
                self.assertRedirects(self.client.get(reverse(ruta)), USUARIOS, fetch_redirect_response=False)

    def test_la_ruta_antigua_sigue_exigiendo_admin(self):
        for ruta in ('crud', 'reporte_alumnos'):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(reverse(ruta))
                self.assertEqual(respuesta.status_code, 302)
                self.assertNotIn('dashboard', respuesta['Location'])  # el anonimo va al login, no al panel

    def test_el_listado_viejo_ya_no_existe(self):
        with self.assertRaises(TemplateDoesNotExist):
            get_template('admin_portal/alumnos_list.html')

    def test_eliminar_vuelve_a_usuarios_con_su_aviso(self):
        self.entrar()
        respuesta = self.client.post(reverse('alumnos_del', args=[self.alumno.id_alumno]), follow=True)
        # El # no llega al servidor: la cadena termina en el dashboard (la direccion con #usuarios se prueba abajo).
        self.assertEqual(respuesta.redirect_chain, [(USUARIOS, 302)])
        self.assertContains(respuesta, 'Bien, datos eliminados...')
        self.assertFalse(Alumno.objects.filter(pk=self.alumno.pk).exists())

    def test_eliminar_responde_con_la_direccion_de_usuarios(self):
        self.entrar()
        respuesta = self.client.post(reverse('alumnos_del', args=[self.alumno.id_alumno]))
        self.assertEqual((respuesta.status_code, respuesta['Location']), (302, USUARIOS))

    def test_el_admin_no_crea_ni_edita_alumnos(self):
        """Decidido 21-nov: crear y editar dejaba al admin con la clave, el correo y el RUT de otra persona. Si hace falta,
        sera una herramienta de soporte con clave temporal y registro; mientras, un superusuario usa /admin/."""
        for nombre in ('alumnos_Add', 'alumnos_findEdit', 'alumnos_Update'):
            with self.subTest(ruta=nombre), self.assertRaises(NoReverseMatch):
                reverse(nombre, args=[1] if nombre == 'alumnos_findEdit' else [])
        self.entrar()
        for url in ('/admin_portal/alumnos_Add', '/admin_portal/alumnos_findEdit/1/', '/admin_portal/alumnos_Update'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {'password': 'x'}).status_code, 404)

    def test_el_menu_de_todas_las_paginas_lleva_a_usuarios_del_dashboard(self):
        self.entrar()
        for pagina in ('dashboard_admin', 'planes_adm', 'nosotros_adm', 'asignaturas_adm'):
            with self.subTest(pagina=pagina):
                html = self.client.get(reverse(pagina)).content.decode()
                self.assertIn(f'<a id="nav-usuarios" class="nav-item " href="{USUARIOS}">', html)
                self.assertNotIn('/admin_portal/crud/', html)
