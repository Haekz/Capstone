"""Las tasas que muestran las pantallas salen de alumnos/paquetes.py, no de las plantillas (21-nov).

Visto el 20-nov: Finanzas del admin y Detalle de liquidaciones del docente decian «15 %», «85 %» y «25 %» a mano. Coincidian con
COMISION y COMISION_VIDEOS, pero con otra tasa quedaban desfasadas, igual que las vigencias de Planes.
"""

import re
from fractions import Fraction
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from alumnos import paquetes
from tests.test_paquetes import RUT_PROFE, Escenario
from tests.test_pulido_docente_cuenta import _seccion
from tests.test_retiros import crear_admin, entrar_admin


class PorcentajesTests(SimpleTestCase):

    def test_una_tasa_entera_se_muestra_sin_decimales(self):
        self.assertEqual(paquetes.porcentaje(Fraction(15, 100)), 15)
        self.assertIsInstance(paquetes.porcentaje(Fraction(15, 100)), int)

    def test_una_tasa_con_decimales_no_se_corta(self):
        """Con int(tasa * 100) el 12,5% se mostraba como 12%."""
        self.assertEqual(paquetes.porcentaje(Fraction(125, 1000)), 12.5)

    def test_las_tasas_vigentes(self):
        self.assertEqual(paquetes.porcentajes(), {'comision_pct': 15, 'pago_profesor_pct': 85, 'comision_videos_pct': 25})

    def test_lo_que_recibe_el_profesor_es_el_resto_de_la_comision(self):
        with mock.patch.object(paquetes, 'COMISION', Fraction(20, 100)):
            self.assertEqual(paquetes.porcentajes()['pago_profesor_pct'], 80)


class NingunaPlantillaEscribeLasTasasTests(SimpleTestCase):
    """Guardia: un 15 %, 85 % o 25 % escrito en una plantilla es el desfase de manana."""

    def test_ninguna_plantilla_de_la_app_las_trae_a_mano(self):
        escritas = []
        for plantilla in settings.BASE_DIR.glob('*/templates/**/*.html'):
            for numero, linea in enumerate(plantilla.read_text(encoding='utf-8').splitlines(), start=1):
                if re.search(r'\b(15|85|25) ?%', linea):
                    escritas.append(f'{plantilla.relative_to(settings.BASE_DIR)}:{numero}')
        self.assertEqual(escritas, [])


class FinanzasDelAdminTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin, cls.tutor = crear_admin()

    def dashboard(self):
        entrar_admin(self.client, self.admin, self.tutor)
        return self.client.get(reverse('dashboard_admin')).content.decode()

    def test_las_leyendas_dicen_las_tasas_vigentes(self):
        html = self.dashboard()
        self.assertIn('15 % de clases y 25 % de videos, si se entrega todo', html)
        self.assertIn('15 % de clases dictadas y 25 % de videos compartidos', html)

    def test_si_cambia_la_tasa_cambian_las_leyendas(self):
        with mock.patch.object(paquetes, 'COMISION', Fraction(20, 100)), \
                mock.patch.object(paquetes, 'COMISION_VIDEOS', Fraction(30, 100)):
            html = self.dashboard()
        self.assertIn('20 % de clases y 30 % de videos, si se entrega todo', html)
        self.assertIn('20 % de clases dictadas y 30 % de videos compartidos', html)
        self.assertNotIn('15 % de clases', html)


class DetalleDeLiquidacionesDelDocenteTests(Escenario):

    def saldo(self):
        self.entrar(RUT_PROFE)
        return _seccion(self.client.get(reverse('panel_profesor')).content.decode(), 'saldo')

    def test_el_detalle_dice_las_tasas_vigentes(self):
        saldo = self.saldo()
        self.assertIn('la comisión de LBWUS (15 %, IVA incluido) y lo que recibes tú (85 %)', saldo)
        self.assertIn('<th>Comisión LBWUS (15 %)</th>', saldo)
        self.assertIn('<th>Tu abono (85 %)</th>', saldo)

    def test_si_cambia_la_tasa_cambia_el_detalle(self):
        with mock.patch.object(paquetes, 'COMISION', Fraction(20, 100)):
            saldo = self.saldo()
        self.assertIn('la comisión de LBWUS (20 %, IVA incluido) y lo que recibes tú (80 %)', saldo)
        self.assertIn('<th>Comisión LBWUS (20 %)</th>', saldo)
        self.assertIn('<th>Tu abono (80 %)</th>', saldo)
