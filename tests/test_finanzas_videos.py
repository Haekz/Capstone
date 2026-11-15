"""B1 (13-nov): las finanzas del admin cuentan los videos (agregado, extras, devoluciones).

Antes, "Cobrado", "Ganancia" y "Por dictar" solo veian PaqueteClases.monto, mientras "Saldo de profesores" ya
incluia los videos: las tarjetas no cuadraban. Mismas reglas que user_profesor/saldos.py: un video se gana al
compartirlo (25% LBWUS, politica seccion 12) y lo devuelto ya no es de nadie en LBWUS.
"""

from alumnos import paquetes
from alumnos.models.videos import DevolucionVideos
from admin_portal.metricas import finanzas
from tests.test_entrega_videos_extra import PENDIENTE, Base
from user_profesor.saldos import calcular_saldos

CLASES = 15000  # Base.paquete(): flexible de 1 clase, sin dictar


class FinanzasConVideosTests(Base):

    def setUp(self):
        super().setUp()
        self.con_videos = self.paquete(videos=1)  # $5.000 de agregado
        self.extra(self.con_videos, 3)  # $13.500: $18.500 por 4 videos
        self.valor = (5000 + 13500) // 4

    def test_cobrado_suma_agregado_y_extras_pagados(self):
        self.extra(self.con_videos, 1, estado=PENDIENTE)  # sin pago confirmado: no entro dinero
        self.assertEqual(finanzas()['cobrado'], CLASES + 5000 + 13500)

    def test_un_video_compartido_es_ganancia_de_lbwus(self):
        self.compartir(self.con_videos, 2)
        self.assertEqual(finanzas()['ganancia'], 2 * paquetes.comision(self.valor, paquetes.COMISION_VIDEOS))

    def test_la_ganancia_cuadra_con_el_saldo_de_los_profesores(self):
        """Lo que no va al profesor es de LBWUS: la misma cuenta, vista desde cada lado (sin retiros)."""
        self.compartir(self.con_videos, 3)
        self.assertEqual(finanzas()['ganancia'], calcular_saldos(self.profe)['pendiente'])

    def test_lo_no_compartido_queda_por_entregar(self):
        self.compartir(self.con_videos, 1)
        self.assertEqual(finanzas()['por_dictar'], CLASES + 5000 + 13500 - self.valor)

    def test_lo_devuelto_sale_de_lo_cobrado_y_de_lo_por_entregar(self):
        DevolucionVideos.objects.create(paquete=self.con_videos, cantidad=2, monto=2 * self.valor)
        cifras = finanzas()
        self.assertEqual(cifras['cobrado'], CLASES + 5000 + 13500 - 2 * self.valor)
        self.assertEqual(cifras['por_dictar'], CLASES + 5000 + 13500 - 2 * self.valor)

    def test_la_comision_estimada_lleva_el_25_de_los_videos(self):
        self.assertEqual(finanzas()['comision_estimada'],
                         paquetes.comision(CLASES) + paquetes.comision(5000 + 13500, paquetes.COMISION_VIDEOS))

    def test_las_tarjetas_cuadran(self):
        """Todo lo cobrado esta ganado por alguien (profesor o LBWUS) o pendiente de dictar o entregar."""
        self.compartir(self.con_videos, 1)
        DevolucionVideos.objects.create(paquete=self.con_videos, cantidad=1, monto=self.valor)
        cifras = finanzas()
        ganado = cifras['ganancia'] + cifras['saldo_profesores']  # sin retiros
        self.assertEqual(cifras['cobrado'], ganado + cifras['por_dictar'])
