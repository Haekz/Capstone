"""Ciclo de pago a profesores: corte, dia de pago y frecuencia (pasos 4a y 4b).

Fechas fijas de 2026 para que los feriados no dependan del dia en que se corre.
En 2026 los lunes feriados son el 29/06 (San Pedro y San Pablo) y el 12/10.
Ultimos viernes: 30/10, 27/11 y 25/12 de 2026; 29/01 de 2027.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.urls import reverse

from alumnos.liquidacion import (
    MENSUAL, SEMANAL, cambiar_frecuencia, dia_de_pago, frecuencia_vigente, proximo_corte, proximo_pago,
)
from tests.test_paquetes import RUT_PROFE, Escenario

MIERCOLES, VIERNES, SABADO = date(2026, 10, 28), date(2026, 10, 30), date(2026, 10, 31)


class CicloSemanalTests(SimpleTestCase):

    def test_el_corte_es_el_viernes_del_ciclo_en_curso(self):
        self.assertEqual(proximo_corte(MIERCOLES, SEMANAL), VIERNES)
        self.assertEqual(proximo_corte(VIERNES, SEMANAL), VIERNES)  # el viernes todavia entra
        self.assertEqual(proximo_corte(SABADO, SEMANAL), date(2026, 11, 6))

    def test_se_paga_el_lunes_siguiente_al_corte(self):
        self.assertEqual(dia_de_pago(VIERNES), date(2026, 11, 2))

    def test_si_el_lunes_es_feriado_se_paga_el_siguiente_dia_habil(self):
        self.assertEqual(dia_de_pago(date(2026, 6, 26)), date(2026, 6, 30))
        self.assertEqual(dia_de_pago(date(2026, 10, 9)), date(2026, 10, 13))


class CicloMensualTests(SimpleTestCase):

    def test_el_corte_es_el_ultimo_viernes_del_mes(self):
        self.assertEqual(proximo_corte(MIERCOLES, MENSUAL), VIERNES)
        self.assertEqual(proximo_corte(VIERNES, MENSUAL), VIERNES)

    def test_pasado_el_corte_toca_el_ultimo_viernes_del_mes_siguiente(self):
        self.assertEqual(proximo_corte(SABADO, MENSUAL), date(2026, 11, 27))
        self.assertEqual(proximo_corte(date(2026, 12, 26), MENSUAL), date(2027, 1, 29))  # cambio de a\u00f1o


class FrecuenciaTests(Escenario):
    """F4: el cambio rige desde el ciclo siguiente. F5: un profesor nuevo parte en semanal."""

    def test_un_profesor_nuevo_cobra_semanal(self):
        self.assertEqual(frecuencia_vigente(self.profe, MIERCOLES), SEMANAL)

    def test_pasar_a_mensual_rige_despues_del_corte_en_curso(self):
        self.assertEqual(cambiar_frecuencia(self.profe, MENSUAL, MIERCOLES), SABADO)
        self.assertEqual(frecuencia_vigente(self.profe, VIERNES), SEMANAL)
        self.assertEqual(proximo_pago(self.profe, VIERNES), date(2026, 11, 2))
        self.assertEqual(frecuencia_vigente(self.profe, SABADO), MENSUAL)
        self.assertEqual(proximo_pago(self.profe, SABADO), date(2026, 11, 30))

    def test_pasar_a_semanal_rige_despues_del_ultimo_viernes_del_mes(self):
        cambiar_frecuencia(self.profe, MENSUAL, MIERCOLES)
        self.assertEqual(cambiar_frecuencia(self.profe, SEMANAL, date(2026, 11, 4)), date(2026, 11, 28))
        self.assertEqual(frecuencia_vigente(self.profe, date(2026, 11, 27)), MENSUAL)

    def test_volver_a_la_vigente_antes_del_corte_anula_el_cambio(self):
        cambiar_frecuencia(self.profe, MENSUAL, MIERCOLES)
        self.assertIsNone(cambiar_frecuencia(self.profe, SEMANAL, MIERCOLES))
        self.profe.refresh_from_db()
        self.assertEqual((self.profe.frecuencia_pago, self.profe.frecuencia_nueva), (SEMANAL, ''))

    def test_rechaza_una_frecuencia_inventada(self):
        with self.assertRaises(ValidationError):
            cambiar_frecuencia(self.profe, 'diaria', MIERCOLES)

    def test_el_profesor_elige_desde_su_panel(self):
        self.entrar(RUT_PROFE)
        respuesta = self.client.post(reverse('guardar_frecuencia_pago'), {'frecuencia': MENSUAL}).json()
        self.assertTrue(respuesta['success'])
        self.assertIn('El ciclo en curso no cambia', respuesta['message'])
        self.assertContains(self.client.get(reverse('panel_profesor')), 'tu pago ser\u00e1 mensual')
