"""La sala de Jitsi no se puede adivinar probando numeros de clase."""

from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings
from django.template.loader import get_template
from django.urls import reverse

from alumnos.models import Asignatura, Clase
from alumnos.sala_virtual import nombre_sala_jitsi
from tests.test_paquetes import RUT_PROFE, Escenario


def nombre_sala(id_clase):
    """El nombre de la sala solo depende del id de la clase (alumnos.sala_virtual.nombre_sala_jitsi)."""
    return nombre_sala_jitsi(SimpleNamespace(id_clase=id_clase))


class NombreDeSalaTests(SimpleTestCase):

    def test_es_siempre_el_mismo_para_la_misma_clase_y_distinto_entre_clases(self):
        self.assertEqual(nombre_sala(7), nombre_sala(7))
        self.assertNotEqual(nombre_sala(7), nombre_sala(8))

    def test_no_se_deduce_del_id(self):
        nombre = nombre_sala(7)
        self.assertTrue(nombre.startswith('lbwus-'))
        self.assertNotIn('clase-privada', nombre)
        self.assertRegex(nombre, r'^lbwus-[0-9a-f]{32}$')

    def test_cambia_con_la_clave_secreta(self):
        con_la_clave_actual = nombre_sala(7)
        with override_settings(SECRET_KEY='otra-clave'):
            self.assertNotEqual(nombre_sala(7), con_la_clave_actual)


class SalaVirtualUsaElNombreSeguroTests(Escenario):

    def test_la_sala_carga_el_nombre_firmado_y_no_el_antiguo(self):
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'), modalidad='online',
                                     profesor=self.profe)
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('sala_virtual', args=[clase.id_clase]))
        self.assertContains(r, f"roomName: '{nombre_sala(clase.id_clase)}'")
        self.assertNotContains(r, 'lbwus-clase-privada')

    def test_el_profesor_ve_la_pantalla_de_espera_con_sus_tildes(self):
        clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'), modalidad='online',
                                     profesor=self.profe)
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('sala_virtual', args=[clase.id_clase]))
        for texto in ('Transmisión Inactiva', 'Completa la información abajo', 'Sobre esta transmisión', 'Resolución de integrales'):
            self.assertContains(r, texto)


class TildesDeLaSalaTests(SimpleTestCase):
    """El archivo llegó con letras perdidas ("Sesin"). Se revisa la fuente entera, así cubre también la rama del alumno."""

    def test_el_template_no_trae_palabras_rotas(self):
        fuente = get_template('alumnos/sala_virtual.html').template.source
        for rota in ('Transmisin', 'informacin', 'pgina', 'recargar cuando', 'transmisin', 'edicin', 'Resolucin',
                     'descripcin', 'estndar', 'empez el', 'sesin', 'cmara', 'micrfono'):
            self.assertNotIn(rota, fuente)
