"""Pago al profesor por los videos que comparte (agregado de videos, fase 4a).

Politica (docs/POLITICA_PAQUETES.md, seccion 12): 75% el profesor y 25% LBWUS, y gana cada vez que comparte un video
(un video atrasado no se paga hasta que lo comparte). Suma al mismo saldo que ya usan su panel y las finanzas del
admin (user_profesor/saldos.py); solo PostgreSQL, sin depender de Mongo.
"""

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import PaqueteClases, SolicitudRetiro
from alumnos.models.videos import VideoCompartido
from tests.test_paquetes import Escenario
from user_profesor.saldos import calcular_saldos, saldos_de


class ValorVideoTests(SimpleTestCase):

    def test_cada_video_vale_su_parte_del_agregado_y_al_profesor_le_queda_el_75(self):
        for plan in paquetes.PLANES:
            with self.subTest(plan=plan.codigo):
                valor = paquetes.valor_video(paquetes.precio_agregado(plan), plan.videos)
                self.assertEqual(valor, paquetes.PRECIO_VIDEO)
                self.assertEqual(paquetes.pago_profesor(valor, paquetes.COMISION_VIDEOS), 3750)


class PagoPorVideosTests(Escenario):

    def paquete(self, profesor=None, alumno=None, plan='progreso', videos=4, dias_restantes=60):
        return PaqueteClases.objects.create(
            alumno=alumno or self.ana, profesor=profesor or self.profe, plan=plan, clases=4, tarifa=15000, monto=59000,
            videos=videos, monto_videos=videos * paquetes.PRECIO_VIDEO, dias=60,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=PaqueteClases.ESTADO_ACTIVA,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))

    def compartir(self, paquete, cuantos=1):
        VideoCompartido.objects.bulk_create(
            [VideoCompartido(paquete=paquete, video_id=f'{paquete.pk:012d}{n:012d}') for n in range(cuantos)])

    def test_sin_compartir_no_gana_nada_aunque_el_alumno_haya_pagado(self):
        self.paquete()  # el pago queda retenido hasta que comparta
        self.assertEqual(calcular_saldos(self.profe), {'total_ganado': 0, 'disponible': 0, 'pendiente': 0})

    def test_cada_video_compartido_le_suma_el_75(self):
        self.compartir(self.paquete(), 2)
        self.assertEqual(calcular_saldos(self.profe), {'total_ganado': 10000, 'disponible': 7500, 'pendiente': 2500})

    def test_suma_videos_de_varios_paquetes_y_alumnos(self):
        self.compartir(self.paquete(), 3)
        self.compartir(self.paquete(alumno=self.beto, plan='flexible', videos=1))
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 4 * 3750)

    def test_lo_ya_entregado_se_paga_aunque_el_paquete_haya_vencido(self):
        self.compartir(self.paquete(dias_restantes=-1))
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 3750)

    def test_los_videos_de_otro_profesor_no_le_suman(self):
        self.compartir(self.paquete(profesor=self.otro), 2)
        self.assertEqual(calcular_saldos(self.profe)['total_ganado'], 0)
        self.assertEqual(calcular_saldos(self.otro)['disponible'], 7500)

    def test_saldos_de_varios_profesores_coincide_con_el_individual(self):
        self.compartir(self.paquete(), 2)
        self.compartir(self.paquete(profesor=self.otro))
        lote = saldos_de([self.profe, self.otro])
        self.assertEqual(lote[self.profe.pk], calcular_saldos(self.profe))
        self.assertEqual(lote[self.otro.pk], calcular_saldos(self.otro))

    # --- fase 5d: soporte retira un video reportado (decidido 09-nov) ---
    def retirar(self, paquete):
        paquete.videos_compartidos.filter(pk=paquete.videos_compartidos.first().pk).update(retirado=timezone.now())

    def test_un_video_retirado_no_se_paga(self):
        paquete = self.paquete()
        self.compartir(paquete, 2)
        self.retirar(paquete)
        self.assertEqual(calcular_saldos(self.profe), {'total_ganado': 5000, 'disponible': 3750, 'pendiente': 1250})

    def test_si_ya_lo_habia_cobrado_se_descuenta_de_lo_proximo(self):
        paquete = self.paquete()
        self.compartir(paquete, 2)
        SolicitudRetiro.objects.create(profesor=self.profe, monto=7500, estado=SolicitudRetiro.PAGADO)
        self.retirar(paquete)
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 0)  # debe 3.750: se muestra 0, no se pierde
        self.compartir(self.paquete(alumno=self.beto, plan='flexible', videos=1))
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 0)  # el video nuevo paga la deuda
        self.compartir(self.paquete(alumno=self.beto, plan='flexible', videos=1))
        self.assertEqual(calcular_saldos(self.profe)['disponible'], 3750)
