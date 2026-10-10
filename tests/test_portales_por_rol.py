"""Tarea 6.6: cada rol entra solo a su portal y ve solo su menu.

Matriz probada: alumno, profesor y administrador (Tutor) contra los tres
portales, mas los casos que mezclaban portales antes del arreglo:

- Un superusuario sin perfil caia en el portal de ALUMNO porque
  CustomUser.rol vale 'alumno' por defecto, y se guardaba user.id como
  alumno_id.
- Un staff sin Tutor entraba al portal admin con admin_id = user.id.
- Un rol con sesion abierta que abria la URL de otro portal era mandado
  al login o al registro, en vez de volver a su propio portal.
"""

from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Alumno, Clase, Genero, Profesor, Tutor

User = get_user_model()

CLAVE = 'clave12345'

PORTAL = {
    'alumno': 'alumno_pag1',
    'profesor': 'panel_profesor',
    'admin': 'dashboard_admin',
}

# Una pantalla interna representativa de cada portal (ademas del inicio).
INTERNAS = {
    'alumno': ['alumno_pag1'],
    'profesor': ['panel_profesor'],
    'admin': ['dashboard_admin', 'crud', 'alumnos_Add', 'planes_adm'],
}


class PortalesPorRolTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        g = Genero.objects.create(descripcion='Otro')
        nac = date(1990, 1, 1)

        u_al = User.objects.create_user('11111111-1', password=CLAVE, rol='alumno')
        cls.alumno = Alumno.objects.create(
            user=u_al, nombre='Ana Alumna', rut='11111111-1', nivel_educacion='media',
            direccion='C1', fecha_nacimiento=nac, correo_electronico='a@lbwus.cl', genero=g,
        )
        u_pr = User.objects.create_user('22222222-2', password=CLAVE, rol='profesor')
        cls.profesor = Profesor.objects.create(
            user=u_pr, nombre='Pedro Profe', rut='22222222-2', especialidad='Mate',
            direccion='C2', fecha_nacimiento=nac, correo_electronico='p@lbwus.cl',
            telefono='911111111', genero=g,
        )
        # rol sin definir a proposito: antes eso lo mandaba al portal alumno.
        u_ad = User.objects.create_user('33333333-3', password=CLAVE)
        cls.tutor = Tutor.objects.create(
            user=u_ad, nombre='Tania Admin', rut='33333333-3', direccion='C3',
            fecha_nacimiento=nac, correo_electronico='t@lbwus.cl', genero=g,
        )
        Clase.objects.create(nombre_curso='Algebra', modalidad='online',
                             horario=time(10, 0), id_profesor=cls.profesor)

        cls.ruts = {'alumno': '11111111-1', 'profesor': '22222222-2', 'admin': '33333333-3'}

    def _login(self, rol):
        return self.client.post(
            reverse('login'), {'username': self.ruts[rol], 'password': CLAVE}
        )

    # ---------- redireccion despues del login ----------

    def test_login_lleva_a_cada_rol_a_su_portal(self):
        for rol, portal in PORTAL.items():
            with self.subTest(rol=rol):
                self.client.logout()
                respuesta = self._login(rol)
                self.assertRedirects(respuesta, reverse(portal), fetch_redirect_response=False)

    def test_sesion_guarda_un_solo_rol_con_el_id_del_perfil(self):
        esperado = {
            'alumno': ('alumno_id', self.alumno.id_alumno),
            'profesor': ('profesor_id', self.profesor.id_profesor),
            'admin': ('admin_id', self.tutor.id_tutor),
        }
        for rol, (clave, valor) in esperado.items():
            with self.subTest(rol=rol):
                self.client.logout()
                self._login(rol)
                sesion = self.client.session
                self.assertEqual(sesion.get(clave), valor)
                otras = {'alumno_id', 'profesor_id', 'admin_id'} - {clave}
                self.assertFalse(any(sesion.get(k) for k in otras))

    def test_volver_al_login_con_sesion_abierta_lleva_al_portal_propio(self):
        for rol, portal in PORTAL.items():
            with self.subTest(rol=rol):
                self.client.logout()
                self._login(rol)
                respuesta = self.client.get(reverse('login'))
                self.assertRedirects(respuesta, reverse(portal), fetch_redirect_response=False)

    # ---------- acceso cruzado ----------

    def test_cada_rol_entra_a_su_portal(self):
        for rol, vistas in INTERNAS.items():
            self.client.logout()
            self._login(rol)
            for vista in vistas:
                with self.subTest(rol=rol, vista=vista):
                    self.assertEqual(self.client.get(reverse(vista)).status_code, 200)

    def test_ningun_rol_entra_a_un_portal_ajeno(self):
        """Si abre la URL de otro portal, vuelve al suyo."""
        for rol in PORTAL:
            self.client.logout()
            self._login(rol)
            for otro, vistas in INTERNAS.items():
                if otro == rol:
                    continue
                for vista in vistas:
                    with self.subTest(rol=rol, intenta=vista):
                        respuesta = self.client.get(reverse(vista))
                        self.assertRedirects(
                            respuesta, reverse(PORTAL[rol]), fetch_redirect_response=False
                        )

    def test_acciones_de_admin_no_corren_con_otro_rol(self):
        for rol in ('alumno', 'profesor'):
            with self.subTest(rol=rol):
                self.client.logout()
                self._login(rol)
                self.client.get(reverse('alumnos_del', args=[self.alumno.id_alumno]))
                self.assertTrue(Alumno.objects.filter(pk=self.alumno.pk).exists())

    def test_endpoints_del_profesor_rechazan_a_otros_roles_en_json(self):
        for rol in ('alumno', 'admin'):
            with self.subTest(rol=rol):
                self.client.logout()
                self._login(rol)
                respuesta = self.client.post(reverse('solicitar_retiro'), {'monto': '1000'})
                self.assertFalse(respuesta.json()['success'])

    def test_logins_especificos_rechazan_rol_equivocado(self):
        respuesta = self.client.post(
            reverse('login_prof'), {'identificador': self.ruts['alumno'], 'password': CLAVE}
        )
        self.assertFalse(respuesta.json()['success'])

        respuesta = self.client.post(
            reverse('login_admin'), {'identificador': self.ruts['profesor'], 'password': CLAVE}
        )
        self.assertFalse(respuesta.json()['success'])
        self.assertIsNone(self.client.session.get('admin_id'))

    # ---------- usuarios sin perfil ----------

    def test_superusuario_sin_perfil_no_cae_en_portal_de_alumno(self):
        User.objects.create_superuser('root', password=CLAVE)
        respuesta = self.client.post(reverse('login'), {'username': 'root', 'password': CLAVE})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no tiene un perfil asignado')
        for clave in ('alumno_id', 'profesor_id', 'admin_id'):
            self.assertIsNone(self.client.session.get(clave))

    # ---------- menus visibles ----------

    def test_menu_global_muestra_el_panel_del_rol(self):
        esperado = {
            'alumno': ('Mi portal', 'Alumno'),
            'profesor': ('Mi panel', 'Profesor'),
            'admin': ('Panel admin', 'Administrador'),
        }
        for rol, (texto, etiqueta) in esperado.items():
            with self.subTest(rol=rol):
                self.client.logout()
                self._login(rol)
                html = self.client.get(reverse('home')).content.decode()
                self.assertIn(texto, html)
                self.assertIn(etiqueta, html)
                self.assertIn(f'href="{reverse(PORTAL[rol])}"', html)
                for otro, portal in PORTAL.items():
                    if otro != rol:
                        self.assertNotIn(f'href="{reverse(portal)}"', html)

    def test_portal_admin_no_muestra_enlaces_de_otros_portales(self):
        self._login('admin')
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertNotIn(f'href="{reverse("alumno_pag1")}"', html)
        self.assertNotIn(f'href="{reverse("panel_profesor")}"', html)
