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

from admin_portal.metricas import finanzas, grafico, planes, registros
from alumnos import paquetes
from alumnos.models import Genero, Inscripcion, PaqueteClases, SolicitudRetiro, Tutor
from tests.test_especialidad import CLAVE
from tests.test_filtros_clases import crear_sesion
from tests.test_matriz_identidad import crear_usuario
from tests.test_paquetes import RUT_ANA, RUT_BETO, Escenario, dar_paquete
from user_profesor.views import calcular_saldos

POR_CLASE_INTENSIVO = 14500  # $116.000 / 8 clases, con la tarifa base
RUT_ADMIN = '66666666-6'


def panel_admin(test, ruta='dashboard_admin', **parametros):
    """Entra como admin y devuelve esa pagina del panel (con ?parametros si se dan)."""
    Tutor.objects.create(user=crear_usuario(RUT_ADMIN, Genero.objects.first()))
    test.entrar(RUT_ADMIN)
    return test.client.get(reverse(ruta), parametros)


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
        for clave in ('cobrado', 'comision_estimada', 'ganancia', 'por_dictar', 'saldo_profesores'):
            self.assertContains(respuesta, '$' + f'{cifras[clave]:,}'.replace(',', '.'))
        self.assertNotContains(respuesta, 'Ingresos Totales')

    def test_comision_estimada_es_el_15_de_lo_cobrado(self):
        self.assertEqual(finanzas()['comision_estimada'], paquetes.comision(116000))

    def test_saldo_de_profesores_es_el_que_ve_cada_uno(self):
        dictado = 2 * paquetes.pago_profesor(POR_CLASE_INTENSIVO)  # dos clases dictadas, sin retiros
        self.assertEqual(finanzas()['saldo_profesores'], dictado)
        SolicitudRetiro.objects.create(profesor=self.profe, monto=10000)  # en tramite: ya no esta disponible
        self.assertEqual(finanzas()['saldo_profesores'], dictado - 10000)
        self.assertEqual(finanzas()['saldo_profesores'], calcular_saldos(self.profe)['disponible'])


class RegistrosPorPeriodoTests(Escenario):
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
        self.assertEqual(registros('mes', self.HOY),
                         [('Oct', 0), ('Nov', 0), ('Dic', 1), ('Ene', 1), ('Feb', 2)])

    def test_cuenta_por_dia(self):
        self.registrar(self.ana, 2026, 2, 15, 10)
        self.registrar(self.profe, 2026, 2, 14, 23, 30)  # hora de Chile: sigue siendo el 14
        self.registrar(self.beto, 2026, 2, 11)
        self.registrar(self.otro, 2026, 2, 10, 23, 59)  # antes del rango
        self.assertEqual(registros('dia', self.HOY),
                         [('11/02', 1), ('12/02', 0), ('13/02', 0), ('14/02', 1), ('15/02', 1)])

    def test_cuenta_por_trimestre(self):
        self.registrar(self.ana, 2026, 2, 3)
        self.registrar(self.beto, 2025, 12, 20)
        self.registrar(self.profe, 2025, 4, 1)
        self.registrar(self.otro, 2024, 12, 31)  # antes del rango
        self.assertEqual(registros('trimestre', self.HOY),
                         [('T1 25', 0), ('T2 25', 1), ('T3 25', 0), ('T4 25', 1), ('T1 26', 1)])

    def test_el_admin_no_cuenta_como_registro(self):
        for perfil in (self.ana, self.beto, self.profe, self.otro, self.sin_titulo):
            self.registrar(perfil, 2025, 1, 1)
        Tutor.objects.create(user=crear_usuario(RUT_ADMIN, Genero.objects.first()))
        self.assertEqual({cantidad for _, cantidad in registros()}, {0})

    def test_el_panel_muestra_el_grafico_real(self):
        respuesta = panel_admin(self)
        resumen = grafico(registros())['resumen']
        self.assertContains(respuesta, f'Alumnos y profesores registrados en los últimos 5 meses: {resumen}')
        self.assertNotContains(respuesta, 'Crecimiento y Actividad')

    def test_el_panel_cambia_de_periodo(self):
        respuesta = panel_admin(self, periodo='trimestre')
        resumen = grafico(registros('trimestre'))['resumen']
        self.assertContains(respuesta, f'registrados en los últimos 5 trimestres: {resumen}')
        self.assertContains(respuesta, 'href="?periodo=trimestre" aria-current="page"')

    def test_un_periodo_desconocido_vuelve_a_meses(self):
        self.assertContains(panel_admin(self, periodo='siglo'), 'registrados en los últimos 5 meses')


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


class PlanesTests(Escenario):
    """La pagina de planes mostraba tres planes por nivel que no existen, a $15.000/$25.000/$35.000 al mes."""

    def test_cuenta_solo_los_paquetes_vigentes(self):
        dar_paquete(self.ana, self.profe, 'intensivo')
        dar_paquete(self.beto, self.profe, 'intensivo')
        dar_paquete(self.beto, self.profe, 'flexible', dias=-1)  # vencido
        dar_paquete(self.ana, self.profe, 'progreso', estado=PaqueteClases.ESTADO_PENDIENTE)  # sin pagar
        self.assertEqual([(c.plan.codigo, c.precio, vigentes) for c, vigentes in planes()],
                         [('flexible', 15000, 0), ('progreso', 59000, 0), ('intensivo', 116000, 2)])

    def test_la_pagina_muestra_los_paquetes_reales(self):
        respuesta = panel_admin(self, 'planes_adm')
        for real in ('Flexible', 'Progreso', 'Intensivo', '$59.000', '$116.000', '0 vigentes'):
            self.assertContains(respuesta, real)
        for falso in ('Plan Básico', 'Educación Media', '$25.000 / mes', '$35.000 / mes'):
            self.assertNotContains(respuesta, falso)
