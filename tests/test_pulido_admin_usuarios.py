"""Portal de admin, etapa A4: Usuarios con el buscador y el boton de la copia, y la ventana propia para confirmar eliminar.

La parte de comportamiento (busqueda sin tildes, aviso de sin resultados, ventana de Swal) vive en mejoras_admin.js y se prueba en el navegador
(verificar_admin_usuarios.py); aqui, lo que el servidor pinta y de lo que depende el JS. Datos ficticios.
"""
import re
from pathlib import Path

from django.urls import reverse

from alumnos.models import Genero
from alumnos.roles import ADMIN
from tests.test_progreso_alumno import crear_alumno
from tests.test_resenas import BaseResenas, entrar

JS = Path(__file__).resolve().parent.parent / 'admin_portal/static/admin_portal/mejoras_admin.js'


class UsuariosDelAdminTests(BaseResenas):

    def setUp(self):
        entrar(self.client, self.admin, ADMIN)

    def pagina(self):
        return self.client.get(reverse('dashboard_admin')).content.decode()

    def test_el_admin_no_crea_ni_edita_alumnos_solo_los_ve_y_los_elimina(self):
        """Decidido 21-nov: crear y editar alumnos desde el admin dejaba al admin con la clave y el correo ajenos."""
        html = self.pagina()
        for viejo in ('Agregar alumno', 'Agregar Usuario', 'add-user-btn', 'title="Editar"', 'alumnos_findEdit'):
            with self.subTest(viejo=viejo):
                self.assertNotIn(viejo, html)
        self.assertIn('title="Eliminar"', html)

    def test_el_buscador_usa_la_clase_de_la_capa_y_se_anuncia_a_los_lectores(self):
        html = self.pagina()
        self.assertIn('<div class="search-bar adm-buscar-usuarios">', html)
        self.assertNotIn('max-width:360px', html)  # el ancho lo da la capa (06c), no un estilo en linea
        self.assertIn('placeholder="Buscar por nombre, RUT o correo…" aria-label="Buscar usuarios por nombre, RUT o correo"', html)

    def test_cada_alumno_se_elimina_con_la_ventana_propia_y_el_confirm_de_respaldo(self):
        html = self.pagina()
        formularios = re.findall(r'<form method="post" action="([^"]+)"\s+class="form-accion" data-confirmar="([^"]*)"\s+'
                                 r'onsubmit="return window\.confirmarEliminar \? window\.confirmarEliminar\(this, event\) : '
                                 r"confirm\('¿Seguro que quieres eliminar a ([^?]*)\?'\)\">", html)
        self.assertEqual(sorted(nombre for _, nombre, _ in formularios), ['Ana', 'Bea'])
        for accion, nombre, en_el_confirm in formularios:
            with self.subTest(alumno=nombre):
                self.assertEqual(nombre, en_el_confirm)
                self.assertTrue(accion.startswith('/admin_portal/alumnos_del/'))

    def test_cada_boton_de_eliminar_dice_a_quien_elimina(self):
        """Solo con title="Eliminar", un lector de pantalla leia lo mismo en cada fila (WCAG 2.4.6 / 4.1.2)."""
        crear_alumno('44444444-4', 'Zoe"><i>', Genero.objects.first())
        html = self.pagina()
        etiquetas = re.findall(r'<button type="submit" class="btn-action delete" title="Eliminar" aria-label="([^"]*)">', html)
        self.assertEqual(sorted(etiquetas), ['Eliminar a Ana', 'Eliminar a Bea', 'Eliminar a Zoe&quot;&gt;&lt;i&gt;'])

    def test_un_nombre_con_comillas_o_etiquetas_no_rompe_el_boton_de_eliminar(self):
        crear_alumno('44444444-4', 'Zoe"><i>', Genero.objects.first())
        html = self.pagina()
        self.assertIn('data-confirmar="Zoe&quot;&gt;&lt;i&gt;"', html)
        self.assertNotIn('Zoe"><i>', html)

    def test_las_filas_traen_lo_que_lee_la_busqueda(self):
        html = self.pagina()
        filas = re.findall(r'<tr class="user-row" data-name="([^"]*)"\s+data-rut="([^"]*)"\s+data-correo="([^"]*)"', html)
        self.assertEqual(len(filas), 5)  # 2 alumnos + 2 profesores + 1 administrador
        self.assertIn(('ana', '11111111-1', '11111111-1@lbwus.cl'), filas)

    def test_el_js_trae_las_partes_de_usuarios(self):
        js = JS.read_text(encoding='utf-8')
        for parte in ('window.filterUsers = ', 'window.showUserTab = ', 'adm-sin-resultados', 'window.confirmarEliminar = ',
                      "customClass: {confirmButton: 'swal-peligro'}", 'focusCancel: true'):
            with self.subTest(parte=parte):
                self.assertIn(parte, js)
        self.assertLessEqual(len(js.splitlines()), 600)
