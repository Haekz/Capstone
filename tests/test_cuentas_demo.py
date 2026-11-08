"""Cuentas de demo (alumnos/management/commands/crear_cuentas_demo.py).

Las cuentas tienen una clave conocida: el comando no debe correr en produccion ni pisar cuentas reales.
La clave no esta en el codigo: llega por la variable CUENTAS_DEMO_CLAVE.
"""

import os
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse

from alumnos.exceptions import InscripcionError
from alumnos.management.commands.crear_cuentas_demo import BUY_ORDER, CUENTAS, VARIABLE_CLAVE
from alumnos.models import Alumno, Genero, Inscripcion, PaqueteClases, Profesor, SesionClase
from alumnos.services import InscripcionService
from apoderados.models import Apoderado, Vinculo
from alumnos.utils import es_menor

User = get_user_model()
RUT = {clave: rut for clave, rut, *_ in CUENTAS}
CLAVE = 'clave-solo-para-pruebas-1'


def con_clave():
    """La variable de entorno que el comando exige, solo durante el bloque."""
    return patch.dict(os.environ, {VARIABLE_CLAVE: CLAVE})


def crear_cuentas():
    with override_settings(DEBUG=True), con_clave():  # el corredor de pruebas fuerza DEBUG=False
        call_command('crear_cuentas_demo', stdout=StringIO())


class CuentasDeDemoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        crear_cuentas()

    def alumno(self, clave):
        return Alumno.objects.get(user__username=RUT[clave])

    def test_crea_las_cinco_cuentas_con_su_rol(self):
        self.assertEqual(User.objects.count(), 5)
        self.assertTrue(Profesor.objects.get(user__username=RUT['profesor']).puede_hacer_clases)
        self.assertEqual(Apoderado.objects.get(user__username=RUT['apoderado']).estado, Apoderado.VERIFICADO)
        self.assertEqual(Alumno.objects.count(), 3)

    def test_el_menor_es_menor_y_su_vinculo_esta_verificado(self):
        menor, apoderado = self.alumno('menor'), Apoderado.objects.get()
        self.assertTrue(es_menor(menor.user))
        self.assertFalse(es_menor(self.alumno('alumno').user))
        self.assertFalse(es_menor(self.alumno('alumno_con_plan').user))
        vinculo = Vinculo.objects.get(alumno=menor)
        self.assertEqual((vinculo.apoderado, vinculo.estado), (apoderado, Vinculo.VERIFICADO))
        self.assertTrue(vinculo.autoriza(menor))  # el apoderado ya puede actuar por el menor

    def test_solo_el_alumno_con_plan_tiene_paquete_vigente(self):
        con_plan = self.alumno('alumno_con_plan')
        paquete = PaqueteClases.objects.get()
        self.assertEqual((paquete.alumno, paquete.estado, paquete.buy_order),
                         (con_plan, PaqueteClases.ESTADO_ACTIVA, BUY_ORDER))
        self.assertEqual(list(PaqueteClases.objects.vigentes()), [paquete])

    def test_el_alumno_con_plan_puede_reservar_y_el_menor_no_por_su_cuenta(self):
        sesion = SesionClase.objects.filter(estado=SesionClase.ESTADO_PROGRAMADA).first()
        reserva = InscripcionService.inscribir_alumno_en_sesion(self.alumno('alumno_con_plan'), sesion.pk)
        self.assertEqual((reserva.paquete, reserva.estado), (PaqueteClases.objects.get(), Inscripcion.ESTADO_CONFIRMADA))
        with self.assertRaises(InscripcionError):
            InscripcionService.inscribir_alumno_en_sesion(self.alumno('menor'), sesion.pk)

    def test_las_cinco_cuentas_inician_sesion_con_su_rut(self):
        for clave, rut in RUT.items():
            with self.subTest(cuenta=clave):
                self.client.logout()
                self.client.post(reverse('login'), {'username': rut, 'password': CLAVE})
                self.assertEqual(self.client.session.get('_auth_user_id'), str(User.objects.get(username=rut).pk))

    def test_correrlo_otra_vez_no_duplica_nada(self):
        antes = [m.objects.count() for m in (User, Alumno, Profesor, Apoderado, Vinculo, PaqueteClases, SesionClase)]
        crear_cuentas()
        self.assertEqual([m.objects.count() for m in (User, Alumno, Profesor, Apoderado, Vinculo, PaqueteClases, SesionClase)],
                         antes)


class SeguridadDelComandoTests(TestCase):

    def test_sin_debug_no_crea_nada(self):
        with override_settings(DEBUG=False):
            with self.assertRaisesMessage(CommandError, 'DEBUG=True'):
                call_command('crear_cuentas_demo', stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)

    def test_sin_la_variable_de_clave_no_crea_nada(self):
        with override_settings(DEBUG=True), patch.dict(os.environ):
            os.environ.pop(VARIABLE_CLAVE, None)
            with self.assertRaisesMessage(CommandError, VARIABLE_CLAVE):
                call_command('crear_cuentas_demo', stdout=StringIO())
        self.assertEqual(User.objects.count(), 0)

    def test_no_pisa_una_cuenta_real_con_el_mismo_rut(self):
        real = User.objects.create_user(RUT['alumno'], rut=RUT['alumno'], email='real@gmail.com', password='la-clave-real',
                                        rol='alumno', genero=Genero.objects.create(descripcion='Otro'))
        with override_settings(DEBUG=True), con_clave():
            with self.assertRaisesMessage(CommandError, 'no es de demo'):
                call_command('crear_cuentas_demo', stdout=StringIO())
        real.refresh_from_db()
        self.assertTrue(real.check_password('la-clave-real'))
        self.assertEqual(User.objects.count(), 1)  # tampoco quedaron a medias las otras cuentas
