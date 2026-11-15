"""Registro de un administrador por otro administrador (user_profesor.views.regis_tutor).

Fijan lo que hace hoy cada validacion y su orden, para poder partir la vista en funciones
chicas sin cambiar su comportamiento (integracion del PR #107 de Franco).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alumnos.models import Genero, Tutor
from tests.test_retiros import crear_admin, entrar_admin

RUT_NUEVO = '12345678-5'  # RUT valido, distinto del admin de las pruebas
CLAVE = 'ClaveSegura99!'
User = get_user_model()


class RegistroDeAdministradorTests(TestCase):

    def setUp(self):
        self.genero = Genero.objects.create(descripcion='Otro')
        self.url = reverse('regis_tutor')

    def entrar(self):
        entrar_admin(self.client, *crear_admin())

    def datos(self, **cambios):
        datos = {
            'nombre': 'Nuevo Admin', 'rut': RUT_NUEVO, 'direccion': 'Av Test 123',
            'fecha_nacimiento': '1990-01-01', 'correo_electronico': 'nuevo@lbwus.cl',
            'telefono': '912345678', 'genero': str(self.genero.id_genero),
            'password': CLAVE, 'confirm_password': CLAVE,
        }
        datos.update(cambios)
        return datos

    def rechazado(self, mensaje, **cambios):
        """POST con un dato malo: la respuesta dice por que y no se crea ninguna cuenta."""
        self.entrar()
        respuesta = self.client.post(self.url, self.datos(**cambios))
        self.assertFalse(respuesta.json()['success'])
        self.assertIn(mensaje, respuesta.json()['message'])
        self.assertFalse(User.objects.filter(rut=RUT_NUEVO).exists())

    def test_quien_no_es_admin_no_entra(self):
        self.assertRedirects(self.client.get(self.url), reverse('login'), fetch_redirect_response=False)
        respuesta = self.client.post(self.url, self.datos())
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(User.objects.filter(rut=RUT_NUEVO).exists())

    def test_el_admin_ve_el_formulario(self):
        self.entrar()
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_el_admin_crea_otro_admin_y_entra_con_su_perfil(self):
        self.entrar()
        respuesta = self.client.post(self.url, self.datos())
        self.assertTrue(respuesta.json()['success'])
        nuevo = User.objects.get(rut=RUT_NUEVO)
        self.assertEqual(nuevo.rol, 'admin')
        self.assertTrue(Tutor.objects.filter(user=nuevo).exists())
        self.assertEqual(self.client.session['admin_id'], Tutor.objects.get(user=nuevo).id_tutor)

    def test_faltan_campos(self):
        self.rechazado('obligatorios', telefono='')

    def test_las_claves_no_coinciden(self):
        self.rechazado('no coinciden', confirm_password='OtraClave99!')

    def test_clave_de_menos_de_6(self):
        self.rechazado('al menos 6', password='Ab1!', confirm_password='Ab1!')

    def test_la_clave_no_puede_ser_el_rut(self):  # Seg-3: no volver a la validacion generica de Django
        self.rechazado('', password=RUT_NUEVO, confirm_password=RUT_NUEVO)

    def test_rut_invalido(self):
        self.rechazado('RUT', rut='12345678-9')

    def test_rut_o_correo_ya_registrados(self):
        self.rechazado('', correo_electronico='66666666-6@lbwus.cl', rut='66666666-6')

    def test_fecha_con_formato_invalido(self):
        self.rechazado('Formato de fecha', fecha_nacimiento='01/01/1990')

    def test_fecha_futura(self):
        self.rechazado('actual ni futura', fecha_nacimiento='2999-01-01')

    def test_menor_de_18(self):
        self.rechazado('18 años', fecha_nacimiento='2015-01-01')

    def test_genero_inexistente_da_error_interno(self):
        self.entrar()
        respuesta = self.client.post(self.url, self.datos(genero='999999'))
        self.assertFalse(respuesta.json()['success'])
        self.assertFalse(User.objects.filter(rut=RUT_NUEVO).exists())
