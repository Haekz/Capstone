"""Ciclo de pago a profesores: corte el viernes, pago el lunes siguiente (paso 4a).

Fechas fijas de 2026 para que los feriados no dependan del dia en que se corre.
En 2026 los lunes feriados son el 29/06 (San Pedro y San Pablo) y el 12/10.
"""

from datetime import date

from django.test import SimpleTestCase

from alumnos.liquidacion import dia_de_pago, proximo_corte

MIERCOLES, VIERNES, SABADO = date(2026, 10, 28), date(2026, 10, 30), date(2026, 10, 31)


class CicloSemanalTests(SimpleTestCase):

    def test_el_corte_es_el_viernes_del_ciclo_en_curso(self):
        self.assertEqual(proximo_corte(MIERCOLES), VIERNES)
        self.assertEqual(proximo_corte(VIERNES), VIERNES)  # el viernes todavia entra
        self.assertEqual(proximo_corte(SABADO), date(2026, 11, 6))

    def test_se_paga_el_lunes_siguiente_al_corte(self):
        self.assertEqual(dia_de_pago(VIERNES), date(2026, 11, 2))

    def test_si_el_lunes_es_feriado_se_paga_el_siguiente_dia_habil(self):
        self.assertEqual(dia_de_pago(date(2026, 6, 26)), date(2026, 6, 30))
        self.assertEqual(dia_de_pago(date(2026, 10, 9)), date(2026, 10, 13))
