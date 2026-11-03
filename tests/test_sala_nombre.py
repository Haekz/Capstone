"""La sala de Jitsi no se puede adivinar probando numeros de clase."""

from datetime import time

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from alumnos.models import Asignatura, Clase
from alumnos.sala import nombre_sala
from tests.test_paquetes import RUT_PROFE, Escenario


class NombreDeSalaTests(SimpleTestCase):

    def test_es_siempre_el_mismo_para_la_misma_clase_y_distinto_entre_clases(self):
        self.assertEqual(nombre_sala(7), nombre_sala(7))
        self.assertNotEqual(nombre_sala(7), nombre_sala(8))

    def test_no_se_deduce_del_id(self):
        nombre = nombre_sala(7)
        self.assertTrue(nombre.startswith('lbwus-'))
        self.assertNotIn('clase-privada', nombre)
        self.assertRegex(nombre, r'^lbwus-[0-9a-f]{24}$')

    def test_cambia_con_la_clave_secreta(self):
        con_la_clave_actual = nombre_sala(7)
        with override_settings(SECRET_KEY='otra-clave'):
            self.assertNotEqual(nombre_sala(7), con_la_clave_actual)


class SalaVirtualUsaElNombreSeguroTests(Escenario):

    def test_la_sala_carga_el_nombre_firmado_y_no_el_antiguo(self):
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'), modalidad='online',
                                     horario=time(10, 0), profesor=self.profe)
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('sala_virtual', args=[clase.id_clase]))
        self.assertContains(r, f"roomName: '{nombre_sala(clase.id_clase)}'")
        self.assertNotContains(r, 'lbwus-clase-privada')
