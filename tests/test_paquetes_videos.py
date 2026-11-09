"""Agregado de videos (Fase 0, decidido 08-nov): cantidades, calendario de entrega, precios y reparto.

alumnos/paquetes.py manda. Si alguien cambia una regla sin actualizar la política, estos tests fallan.
"""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from alumnos import paquetes

PLANES = paquetes.POR_CODIGO


class VideosPorPlanTests(SimpleTestCase):

    def test_cada_plan_trae_1_4_y_6_videos(self):
        self.assertEqual([p.videos for p in paquetes.PLANES], [1, 4, 6])

    def test_el_basico_entrega_su_video_a_las_2_semanas(self):
        self.assertEqual(PLANES['flexible'].entregas, ((14, 1),))

    def test_progreso_e_intensivo_entregan_2_videos_por_mes(self):
        self.assertEqual(PLANES['progreso'].entregas, ((30, 2), (60, 2)))
        self.assertEqual(PLANES['intensivo'].entregas, ((30, 2), (60, 2), (90, 2)))

    def test_ninguna_entrega_vence_despues_del_paquete(self):
        for plan in paquetes.PLANES:
            with self.subTest(plan=plan.codigo):
                dias = [dia for dia, _ in plan.entregas]
                self.assertEqual(dias, sorted(dias))
                self.assertLessEqual(dias[-1], plan.vigencia_dias)


class PrecioVideosTests(SimpleTestCase):

    def test_el_agregado_cuesta_5000_por_video(self):
        precios = {p.codigo: paquetes.precio_agregado(p) for p in paquetes.PLANES}
        self.assertEqual(precios, {'flexible': 5000, 'progreso': 20000, 'intensivo': 30000})

    def test_videos_extra_con_promocion_3_por_13500(self):
        esperado = {1: 5000, 2: 10000, 3: 13500, 4: 18500, 5: 23500, 6: 27000}
        for cantidad, monto in esperado.items():
            with self.subTest(cantidad=cantidad):
                self.assertEqual(paquetes.precio_videos_extra(cantidad), monto)

    def test_videos_extra_entre_1_y_6(self):
        for cantidad in (0, -1, 7):
            with self.subTest(cantidad=cantidad), self.assertRaises(ValidationError):
                paquetes.precio_videos_extra(cantidad)


class RepartoVideosTests(SimpleTestCase):

    def test_lbwus_se_queda_el_25_y_el_profesor_el_75(self):
        for monto, lbwus in ((5000, 1250), (13500, 3375), (30000, 7500)):
            with self.subTest(monto=monto):
                self.assertEqual(paquetes.comision(monto, paquetes.COMISION_VIDEOS), lbwus)
                self.assertEqual(paquetes.pago_profesor(monto, paquetes.COMISION_VIDEOS), monto - lbwus)

    def test_las_clases_siguen_con_el_15(self):
        self.assertEqual(paquetes.comision(59000), 8850)
        self.assertEqual(paquetes.pago_profesor(59000), 50150)
