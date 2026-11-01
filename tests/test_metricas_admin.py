"""Paso 8: cifras reales del panel del admin (admin_portal/metricas.py).

Antes, "Ingresos Totales" era max(inscripciones x 15.000, 180.000): con cero
ventas mostraba $180.000. Ahora siguen docs/POLITICA_PAQUETES.md: lo cobrado por
clases no dictadas es una obligacion y LBWUS gana su 15% solo por las dictadas.
"""

from django.test import TestCase
from django.urls import reverse

from admin_portal.metricas import finanzas
from alumnos import paquetes
from alumnos.models import Genero, Inscripcion, PaqueteClases, Tutor
from tests.test_especialidad import CLAVE
from tests.test_filtros_clases import crear_sesion
from tests.test_matriz_identidad import crear_usuario
from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario, dar_paquete
from user_profesor.views import calcular_saldos

POR_CLASE_INTENSIVO = 14500  # $116.000 / 8 clases, con la tarifa base


class FinanzasTests(Escenario):

    def setUp(self):
        self.intensivo = dar_paquete(self.ana, self.profe, 'intensivo')  # $116.000
        for dias in (-1, -2):  # dos clases dictadas
            Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=self.intensivo,
                                       sesion=crear_sesion(self.clase, dias=dias))
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=self.intensivo,
                                   sesion=crear_sesion(self.clase, dias=1))  # reservada, aun no dictada

    def test_sin_ventas_todo_en_cero(self):
        Inscripcion.objects.all().delete()  # SET_NULL: si no, quedarian como clases sin paquete
        PaqueteClases.objects.all().delete()
        self.assertEqual(set(finanzas().values()), {0})  # antes el panel decia $180.000

    def test_cobrado_ganancia_y_por_dictar(self):
        cifras = finanzas()
        self.assertEqual(cifras['cobrado'], 116000)
        self.assertEqual(cifras['ganancia'], 2 * paquetes.comision(POR_CLASE_INTENSIVO))  # solo lo dictado
        self.assertEqual(cifras['por_dictar'], 116000 - 2 * POR_CLASE_INTENSIVO)

    def test_la_ganancia_es_lo_que_no_va_al_profesor(self):
        """La misma cuenta que el saldo del profesor, vista desde LBWUS."""
        self.assertEqual(finanzas()['ganancia'], calcular_saldos(self.profe)['pendiente'])  # sin retiros

    def test_solo_cuentan_pagos_aprobados(self):
        dar_paquete(self.beto, self.profe, 'flexible', estado=PaqueteClases.ESTADO_PENDIENTE)
        dar_paquete(self.beto, self.profe, 'flexible', estado=PaqueteClases.ESTADO_RECHAZADA)
        self.assertEqual(finanzas()['cobrado'], 116000)

    def test_un_paquete_vencido_sin_usar_no_pasa_a_ser_ganancia(self):
        dar_paquete(self.beto, self.profe, 'flexible', dias=-1)  # $15.000, vencido, ninguna clase
        cifras = finanzas()
        self.assertEqual(cifras['ganancia'], 2 * paquetes.comision(POR_CLASE_INTENSIVO))
        self.assertEqual(cifras['por_dictar'], 116000 + 15000 - 2 * POR_CLASE_INTENSIVO)

    def test_el_panel_muestra_las_cifras(self):
        Tutor.objects.create(user=crear_usuario('66666666-6', Genero.objects.first()))
        self.entrar('66666666-6')
        respuesta = self.client.get(reverse('dashboard_admin'))
        cifras = finanzas()
        for clave in ('cobrado', 'ganancia', 'por_dictar'):
            self.assertContains(respuesta, '$' + f'{cifras[clave]:,}'.replace(',', '.'))
        self.assertNotContains(respuesta, 'Ingresos Totales')
