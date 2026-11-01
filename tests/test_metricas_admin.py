"""Paso 8: cifras reales del panel del admin (admin_portal/metricas.py).

Antes, "Ingresos Totales" era max(inscripciones x 15.000, 180.000): con cero
ventas mostraba $180.000. Ahora siguen docs/POLITICA_PAQUETES.md: lo cobrado por
clases no dictadas es una obligacion y LBWUS gana su 15% solo por las dictadas.
"""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from admin_portal.metricas import finanzas, grafico, registros_por_mes
from alumnos import paquetes
from alumnos.models import Genero, Inscripcion, PaqueteClases, Tutor
from tests.test_especialidad import CLAVE
from tests.test_filtros_clases import crear_sesion
from tests.test_matriz_identidad import crear_usuario
from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario, dar_paquete
from user_profesor.views import calcular_saldos

POR_CLASE_INTENSIVO = 14500  # $116.000 / 8 clases, con la tarifa base
RUT_ADMIN = '66666666-6'


def panel_admin(test):
    """Entra como admin y devuelve el dashboard."""
    Tutor.objects.create(user=crear_usuario(RUT_ADMIN, Genero.objects.first()))
    test.entrar(RUT_ADMIN)
    return test.client.get(reverse('dashboard_admin'))


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
        respuesta = panel_admin(self)
        cifras = finanzas()
        for clave in ('cobrado', 'ganancia', 'por_dictar'):
            self.assertContains(respuesta, '$' + f'{cifras[clave]:,}'.replace(',', '.'))
        self.assertNotContains(respuesta, 'Ingresos Totales')


class RegistrosPorMesTests(Escenario):
    """Escenario registra 2 alumnos (ana, beto) y 3 profesores; aqui se fija cuando."""

    HOY = date(2026, 2, 15)  # los ultimos 5 meses van de Oct a Feb: cruzan el cambio de anio

    def registrar(self, perfil, *fecha):
        get_user_model().objects.filter(pk=perfil.user_id).update(
            date_joined=timezone.make_aware(datetime(*fecha)))

    def test_cuenta_alumnos_y_profesores_por_mes(self):
        self.registrar(self.ana, 2026, 2, 3)
        self.registrar(self.profe, 2026, 2, 10)
        self.registrar(self.beto, 2025, 12, 20)
        self.registrar(self.sin_titulo, 2026, 1, 31, 23, 30)  # medianoche en hora local: sigue en enero
        self.registrar(self.otro, 2025, 9, 30)  # antes del rango
        self.assertEqual(registros_por_mes(self.HOY),
                         [('Oct', 0), ('Nov', 0), ('Dic', 1), ('Ene', 1), ('Feb', 2)])

    def test_el_admin_no_cuenta_como_registro(self):
        for perfil in (self.ana, self.beto, self.profe, self.otro, self.sin_titulo):
            self.registrar(perfil, 2025, 1, 1)
        Tutor.objects.create(user=crear_usuario(RUT_ADMIN, Genero.objects.first()))
        self.assertEqual({cantidad for _, cantidad in registros_por_mes()}, {0})

    def test_el_panel_muestra_el_grafico_real(self):
        respuesta = panel_admin(self)
        resumen = grafico(registros_por_mes())['resumen']
        self.assertContains(respuesta, f'Alumnos y profesores registrados por mes: {resumen}')
        self.assertNotContains(respuesta, 'Crecimiento y Actividad')


class GraficoTests(SimpleTestCase):

    def test_coordenadas_dentro_del_svg(self):
        g = grafico([('Oct', 0), ('Nov', 3), ('Dic', 6), ('Ene', 1), ('Feb', 2)])
        self.assertEqual([(p['x'], p['y']) for p in g['puntos']],
                         [(90, 180.0), (190, 105.0), (290, 30.0), (390, 155.0), (490, 130.0)])
        self.assertEqual([(m['valor'], m['y']) for m in g['marcas']], [(6, 30), (4, 80), (2, 130), (0, 180)])
        self.assertEqual(g['linea'], 'M 90 180.0 L 190 105.0 L 290 30.0 L 390 155.0 L 490 130.0')
        self.assertEqual(g['area'], g['linea'] + ' L 490 180 L 90 180 Z')
        self.assertEqual(g['resumen'], 'Oct: 0, Nov: 3, Dic: 6, Ene: 1, Feb: 2')

    def test_el_tope_es_multiplo_de_3_para_marcas_enteras(self):
        self.assertEqual(grafico([('Ene', 7)])['marcas'][0]['valor'], 9)

    def test_sin_registros_la_linea_queda_en_cero(self):
        g = grafico([('Ene', 0), ('Feb', 0)])
        self.assertEqual({p['y'] for p in g['puntos']}, {180.0})
        self.assertEqual([m['valor'] for m in g['marcas']], [3, 2, 1, 0])
