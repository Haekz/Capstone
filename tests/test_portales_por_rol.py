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

from alumnos.models import Alumno, Asignatura, Clase, Especialidad, Genero, Profesor, Tutor

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

        # Datos personales en CustomUser; los perfiles solo guardan lo suyo.
        u_al = User.objects.create_user(
            '11111111-1', password=CLAVE, rol='alumno', rut='11111111-1',
            first_name='Ana', last_name='Alumna', email='a@lbwus.cl',
            direccion='C1', fecha_nacimiento=nac, genero=g,
        )
        cls.alumno = Alumno.objects.create(user=u_al, nivel_educacion='media')
        u_pr = User.objects.create_user(
            '22222222-2', password=CLAVE, rol='profesor', rut='22222222-2',
            first_name='Pedro', last_name='Profe', email='p@lbwus.cl',
            direccion='C2', fecha_nacimiento=nac, telefono='911111111', genero=g,
        )
        cls.profesor = Profesor.objects.create(
            user=u_pr, especialidad=Especialidad.objects.create(nombre='Mate'),
        )
        # rol sin definir a proposito: antes eso lo mandaba al portal alumno.
        u_ad = User.objects.create_user(
            '33333333-3', password=CLAVE, rut='33333333-3',
            first_name='Tania', last_name='Admin', email='t@lbwus.cl',
            direccion='C3', fecha_nacimiento=nac, genero=g,
        )
        cls.tutor = Tutor.objects.create(user=u_ad)
        Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Algebra'),
                             modalidad='online', horario=time(10, 0), profesor=cls.profesor)

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
