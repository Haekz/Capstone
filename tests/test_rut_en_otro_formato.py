"""Un RUT es el mismo escrito con o sin puntos y guion, con k o K (20-nov).

usuario_existe (todos los registros: alumno, profesor, apoderado, Google) y crear_admin comparaban el texto tal cual: con
'12.345.678-5' se creaba una segunda cuenta de quien ya era '12345678-5', y la restriccion unique de la base no lo frena
porque los textos difieren. El login ya aceptaba todos los formatos. Datos ficticios.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from alumnos.management.commands.crear_admin import DatosAdminForm
from alumnos.utils import RUT_YA_REGISTRADO, rut_en_uso, usuario_existe


class RutEnOtroFormatoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear = get_user_model().objects.create_user
        cls.con_guion = crear(username='12345678-5', rut='12345678-5', email='ana@lbwus.cl', password='Clave-Prueba-1')
        cls.con_k_minuscula = crear(username='11222338-k', rut='11222338-k', email='beto@lbwus.cl', password='Clave-Prueba-1')

    def test_el_mismo_rut_en_cualquier_formato_ya_esta_registrado(self):
        for rut in ('12345678-5', '12.345.678-5', '123456785', ' 12.345.678-5 ', '11222338-K', '11.222.338-K',
                    '11222338K', '11.222.338-k'):
            with self.subTest(rut=rut):
                self.assertTrue(rut_en_uso(rut))
                self.assertEqual(usuario_existe(rut, ''), RUT_YA_REGISTRADO)

    def test_otro_rut_y_la_propia_cuenta_no_chocan(self):
        self.assertFalse(rut_en_uso('11.111.111-1'))
        self.assertFalse(rut_en_uso(''))
        self.assertFalse(rut_en_uso('12.345.678-5', excluir_user=self.con_guion))  # editar su perfil sigue funcionando
        self.assertIsNone(usuario_existe('12.345.678-5', 'ana@lbwus.cl', excluir_user=self.con_guion))

    def test_crear_admin_no_crea_una_cuenta_con_un_rut_o_correo_que_ya_existen(self):
        for rut, correo in (('12.345.678-5', 'ANA@lbwus.cl'), ('11.222.338-K', 'Beto@LBWUS.cl')):
            with self.subTest(rut=rut):
                errores = DatosAdminForm(data={'rut': rut, 'first_name': 'Tamara', 'last_name': 'Soto', 'email': correo}).errors
                self.assertEqual(errores['rut'], ['Ya existe un usuario con ese RUT.'])
                self.assertEqual(errores['email'], ['Ya existe un usuario con ese correo.'])
