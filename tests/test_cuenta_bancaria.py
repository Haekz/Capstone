"""Cuenta bancaria del profesor: una sola, a su nombre, cifrada y enmascarada (paso 3a).

DECISIONES_SOPORTE_Y_PAGOS.md, P2: solo cuentas cuyo titular es el mismo profesor.
"""

import base64
import hashlib
import re
import time
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.cifrado import cifrador
from alumnos.models import CuentaBancaria, Inscripcion, SolicitudRetiro
from tests.test_especialidad import CLAVE
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_OTRO, RUT_PROFE, Escenario, dar_paquete
from tests.test_retiros import crear_admin, entrar_admin

NUMERO = '9876543210'
CUENTA = {'banco': 'BancoEstado', 'tipo_cuenta': 'rut_vista', 'numero_cuenta': NUMERO}
NUEVA = {'banco': 'Banco de Chile', 'tipo_cuenta': 'corriente', 'numero_cuenta': '11112222'}


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


class CambioCuentaTests(Escenario):
    """Paso 3b: cambiar una cuenta existente exige contrasena, enlace al correo y 48 h sin pagos."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin, cls.tutor = crear_admin()

    def setUp(self):
        self.entrar(RUT_PROFE)
        self.client.post(reverse('guardar_cuenta_bancaria'), CUENTA)
        mail.outbox.clear()

    def pedir(self, password=CLAVE):
        return self.client.post(reverse('guardar_cuenta_bancaria'), {**NUEVA, 'password': password}).json()

    def enlace(self):
        return re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)

    def cuenta(self):
        return CuentaBancaria.objects.get(profesor=self.profe)

    def test_sin_la_contrasena_correcta_no_pide_el_cambio(self):
        for password in ('', 'otra-clave'):
            with self.subTest(password=password):
                self.assertFalse(self.pedir(password)['success'])
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.cuenta().numero, NUMERO)

    def test_el_cambio_se_aplica_solo_al_abrir_el_enlace_y_avisa(self):
        self.assertTrue(self.pedir()['success'])
        self.assertEqual(self.cuenta().numero, NUMERO)
        self.assertNotIn('11112222', mail.outbox[0].body)

        respuesta = self.client.get(self.enlace(), follow=True)
        self.assertContains(respuesta, 'Cuenta cambiada a Banco de Chile')
        cuenta = self.cuenta()
        self.assertEqual((cuenta.banco, cuenta.tipo_cuenta, cuenta.numero), ('Banco de Chile', 'corriente', '11112222'))
        self.assertTrue(cuenta.bloqueada)
        self.assertIn('Tu cuenta bancaria cambió', mail.outbox[1].subject)

    def test_el_enlace_sirve_una_sola_vez(self):
        self.pedir()
        enlace = self.enlace()
        self.client.get(enlace)
        self.assertContains(self.client.get(enlace, follow=True), 'ya se usó')

    def test_el_enlace_vence_a_las_24_horas(self):
        self.pedir()
        with patch('django.core.signing.time.time', return_value=time.time() + 25 * 3600):
            respuesta = self.client.get(self.enlace(), follow=True)
        self.assertContains(respuesta, 'venció')
        self.assertEqual(self.cuenta().numero, NUMERO)

    def test_el_enlace_no_sirve_con_la_sesion_de_otro_profesor(self):
        self.pedir()
        enlace = self.enlace()
        self.entrar(RUT_OTRO)
        self.assertContains(self.client.get(enlace, follow=True), 'ya se usó')
        self.assertEqual(self.cuenta().numero, NUMERO)

    def test_no_se_paga_a_una_cuenta_recien_cambiada(self):
        self.pedir()
        self.client.get(self.enlace())
        retiro = SolicitudRetiro.objects.create(profesor=self.profe, monto=5000)
        retiro.aprobar(self.admin)

        entrar_admin(self.client, self.admin, self.tutor)
        dashboard = self.client.get(reverse('dashboard_admin'))
        self.assertContains(dashboard, 'no pagar hasta')
        self.assertNotContains(dashboard, '11112222')
        with self.assertRaisesMessage(ValidationError, 'menos de 48 h'):
            retiro.marcar_pagado(self.admin, 'OP-1')

        CuentaBancaria.objects.filter(profesor=self.profe).update(cambiada_en=timezone.now() - timedelta(hours=49))
        retiro.marcar_pagado(self.admin, 'OP-1')
        self.assertEqual(retiro.estado, SolicitudRetiro.PAGADO)


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
