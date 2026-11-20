"""Un profesor sin especialidad no muestra "None" en el panel del admin ni en Documentos de profesores.

La especialidad puede quedar vacia (null=True, y SET_NULL si se borra la especialidad). Se muestra "—".
"""

from django.test import TestCase
from django.urls import reverse

from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_especialidad import crear_profesor
from tests.test_retiros import crear_admin, entrar_admin


class EspecialidadVaciaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_profesor('20000000-1', 'sin@lbwus.cl', None)

    def test_panel_admin(self):
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        html = self.client.get(reverse('dashboard_admin')).content.decode()
        self.assertNotIn('>None<', html)
        self.assertIn('badge-profesor">\u2014<', html)  # tabla de usuarios
        self.assertIn('user-cell-sub">\u2014<', html)  # ultimos profesores del resumen

    def test_documentos_de_profesores_del_lider(self):
        entrar_soporte(self.client, crear_agente('10000003-5', lider=True))
        html = self.client.get(reverse('titulos_adm')).content.decode()
        self.assertNotIn('<td>None</td>', html)
        self.assertIn('<td>\u2014</td>', html)  # "Resto de profesores"
