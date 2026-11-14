"""Grafico de solicitudes por mes del panel del profesor (user_profesor.views._rendimiento_mensual).

Funcion pura: recibe las inscripciones y el mes actual, asi se prueba sin reloj ni base de datos.
Fija el comportamiento de siempre antes de sacarla de panel_profesor (integracion del PR #107 de Franco).
"""

from datetime import datetime
from types import SimpleNamespace

from django.test import SimpleTestCase

from user_profesor.views import _rendimiento_mensual


def inscripcion(mes):
    return SimpleNamespace(fecha_inscripcion=datetime(2026, mes, 15))


class RendimientoMensualTests(SimpleTestCase):

    def test_son_los_ultimos_5_meses_el_actual_al_final(self):
        meses = [m['mes'] for m in _rendimiento_mensual([], mes_actual=11)]
        self.assertEqual(meses, ['Jul', 'Ago', 'Sep', 'Oct', 'Nov'])

    def test_cruza_el_cambio_de_año(self):
        meses = [m['mes'] for m in _rendimiento_mensual([], mes_actual=2)]
        self.assertEqual(meses, ['Oct', 'Nov', 'Dic', 'Ene', 'Feb'])

    def test_un_mes_sin_inscripciones_vale_cero(self):
        self.assertEqual(_rendimiento_mensual([], mes_actual=11)[-1], {'mes': 'Nov', 'cantidad': 0, 'porcentaje': 0})

    def test_cuenta_por_mes_y_calcula_el_porcentaje_sobre_40(self):
        grafico = _rendimiento_mensual([inscripcion(11)] * 10 + [inscripcion(10)] * 2, mes_actual=11)
        self.assertEqual(grafico[-1], {'mes': 'Nov', 'cantidad': 10, 'porcentaje': 25})
        self.assertEqual(grafico[-2], {'mes': 'Oct', 'cantidad': 2, 'porcentaje': 5})

    def test_el_porcentaje_no_pasa_de_100(self):
        self.assertEqual(_rendimiento_mensual([inscripcion(11)] * 60, mes_actual=11)[-1]['porcentaje'], 100)

    def test_una_inscripcion_sin_fecha_no_cuenta(self):
        sin_fecha = SimpleNamespace(fecha_inscripcion=None)
        self.assertEqual(_rendimiento_mensual([sin_fecha], mes_actual=11)[-1]['cantidad'], 0)
