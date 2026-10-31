"""Cuenta bancaria del profesor: una sola, a su nombre, cifrada y enmascarada (paso 3a).

DECISIONES_SOPORTE_Y_PAGOS.md, P2: solo cuentas cuyo titular es el mismo profesor.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.cifrado import cifrador
from alumnos.models import CuentaBancaria, Inscripcion, SolicitudRetiro
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete
from tests.test_retiros import crear_admin, entrar_admin

NUMERO = '9876543210'
CUENTA = {'banco': 'BancoEstado', 'tipo_cuenta': 'rut_vista', 'numero_cuenta': NUMERO}


class CifradoTests(SimpleTestCase):

    def test_los_documentos_ya_guardados_se_siguen_leyendo(self):
        """cifrador() debe derivar la misma clave que usaba apoderados/documentos.py."""
        clave_anterior = base64.urlsafe_b64encode(
            hashlib.sha256(f'documentos-apoderados:{settings.SECRET_KEY}'.encode()).digest())
        guardado = Fernet(clave_anterior).encrypt(b'carnet')
        self.assertEqual(cifrador('documentos-apoderados').decrypt(guardado), b'carnet')

    def test_cada_proposito_usa_su_propia_clave(self):
        guardado = cifrador('cuentas-bancarias').encrypt(b'123')
        with self.assertRaises(InvalidToken):
            cifrador('documentos-apoderados').decrypt(guardado)


class CuentaBancariaTests(Escenario):

    def guardar(self, **cambios):
        self.entrar(RUT_PROFE)
        return self.client.post(reverse('guardar_cuenta_bancaria'), {**CUENTA, **cambios}).json()

    def test_guarda_el_numero_cifrado_y_lo_muestra_enmascarado(self):
        self.assertTrue(self.guardar(numero_cuenta='98-765 43210')['success'])
        cuenta = CuentaBancaria.objects.get(profesor=self.profe)
        self.assertNotIn(NUMERO.encode(), bytes(cuenta.numero_cifrado))
        self.assertEqual((cuenta.numero, cuenta.enmascarado), (NUMERO, '\u2022\u2022\u2022\u2022 3210'))

    def test_rechaza_datos_fuera_de_las_listas_o_numero_invalido(self):
        malos = {
            'banco que no existe': {'banco': 'Banco Falso'},
            'tipo que no existe': {'tipo_cuenta': 'bitcoin'},
            'numero con letras': {'numero_cuenta': '12AB5678'},
            'numero muy corto': {'numero_cuenta': '1234'},
        }
        for caso, cambio in malos.items():
            with self.subTest(caso):
                self.assertFalse(self.guardar(**cambio)['success'])
        self.assertFalse(CuentaBancaria.objects.exists())

    def test_cambiar_la_cuenta_reemplaza_la_anterior(self):
        self.guardar()
        self.guardar(banco='Banco de Chile', tipo_cuenta='corriente', numero_cuenta='11112222')
        cuenta = CuentaBancaria.objects.get()
        self.assertEqual((cuenta.banco, cuenta.numero), ('Banco de Chile', '11112222'))


class RetiroConCuentaTests(Escenario):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin, cls.tutor = crear_admin()

    def setUp(self):
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                   sesion=crear_sesion(self.clase, dias=-1))
        self.entrar(RUT_PROFE)

    def retirar(self):
        # Los datos bancarios del formulario se ignoran: manda la cuenta registrada.
        return self.client.post(reverse('solicitar_retiro'),
                                {'monto': '5000', 'banco': 'Banco Falso', 'numero_cuenta': '111'}).json()

    def test_sin_cuenta_registrada_no_se_puede_retirar(self):
        respuesta = self.retirar()
        self.assertFalse(respuesta['success'])
        self.assertIn('Registra tu cuenta bancaria', respuesta['message'])
        self.assertFalse(SolicitudRetiro.objects.exists())

    def test_el_retiro_usa_la_cuenta_registrada_y_guarda_solo_lo_enmascarado(self):
        self.client.post(reverse('guardar_cuenta_bancaria'), CUENTA)
        self.assertTrue(self.retirar()['success'])
        retiro = SolicitudRetiro.objects.get()
        self.assertEqual((retiro.banco.nombre, retiro.tipo_cuenta, retiro.numero_cuenta),
                         ('BancoEstado', 'rut_vista', '\u2022\u2022\u2022\u2022 3210'))

    def test_el_admin_ve_el_numero_completo_solo_al_momento_de_pagar(self):
        self.client.post(reverse('guardar_cuenta_bancaria'), CUENTA)
        self.retirar()
        entrar_admin(self.client, self.admin, self.tutor)
        self.assertNotContains(self.client.get(reverse('dashboard_admin')), NUMERO)

        SolicitudRetiro.objects.get().aprobar(self.admin)
        respuesta = self.client.get(reverse('dashboard_admin'))
        self.assertContains(respuesta, f'N.\u00ba {NUMERO}')
        self.assertContains(respuesta, f'RUT {RUT_PROFE}')
