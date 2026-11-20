"""Videos extra, paso 6d: un extra pagado se entrega (cupo y plazo), se paga al profesor y se le avisa.

Solo cuentan las compras ACTIVAS (pago confirmado): una pendiente o rechazada no suma cupo, ni plazo, ni saldo.
Cada compra tiene su propio plazo (pago + 14 dias), aparte de las fechas del plan. Un paquete que no contrato el
agregado al inicio tambien puede recibir extras. El valor por video es el promedio de lo pagado (base + extra).
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.models.videos import CompraVideosExtra
from alumnos.webpay import registrar_respuesta
from comunidad.tests.base import GridFsTestCase
from notificaciones.models import Notificacion
from soporte.models import Ticket
from tests.test_paquetes import Escenario
from tests.test_videoteca import archivo
from user_profesor import entregas, plazos_videos, videoteca
from user_profesor.saldos import calcular_saldos

ACTIVA, PENDIENTE = CompraVideosExtra.ESTADO_ACTIVA, CompraVideosExtra.ESTADO_PENDIENTE


class Base(GridFsTestCase, Escenario):

    def setUp(self):
        super().setUp()
        self.videos = [videoteca.subir(self.profe.id_profesor, self.clase.asignatura_id, f'Video {n}', archivo())
                       for n in range(6)]

    def paquete(self, videos=0, monto_videos=None, plan='flexible', alumno=None, dias_restantes=20):
        """Flexible (30 dias) que lleva 10 dias de vida: su unica fecha del plan es el dia 14."""
        return PaqueteClases.objects.create(
            alumno=alumno or self.ana, profesor=self.profe, plan=plan, clases=1, tarifa=15000, monto=15000, dias=30,
            videos=videos, monto_videos=videos * paquetes.PRECIO_VIDEO if monto_videos is None else monto_videos,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=PaqueteClases.ESTADO_ACTIVA,
            fecha_fin=timezone.now() + timedelta(days=dias_restantes))

    def extra(self, paquete, cantidad, estado=ACTIVA, pagada_hace=0):
        return CompraVideosExtra.objects.create(
            paquete=paquete, cantidad=cantidad, monto=paquetes.precio_videos_extra(cantidad),
            buy_order=f'VX{CompraVideosExtra.objects.count():024d}', estado=estado,
            fecha_pago=timezone.now() - timedelta(days=pagada_hace) if estado == ACTIVA else None)

    def compartir(self, paquete, cuantos):
        for video in self.videos[:cuantos]:
            entregas.compartir(self.profe.id_profesor, paquete.pk, video)

    def fila(self):
        [fila] = entregas.pendientes(self.profe.id_profesor)
        return fila


class CupoTests(Base):

    def test_los_extra_pagados_suman_al_cupo(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 2)
        self.compartir(paquete, 3)
        with self.assertRaisesMessage(ValidationError, 'Ya compartiste los 3 videos'):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.videos[3])

    def test_pendiente_o_rechazada_no_suma(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 2, estado=PENDIENTE)
        self.extra(paquete, 2, estado=CompraVideosExtra.ESTADO_RECHAZADA)
        self.compartir(paquete, 1)
        with self.assertRaisesMessage(ValidationError, 'Ya compartiste los 1 videos'):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.videos[1])

    def test_un_paquete_sin_agregado_recibe_solo_lo_que_compro_como_extra(self):
        sin_nada = self.paquete()
        with self.assertRaisesMessage(ValidationError, 'No encontramos un paquete vigente con videos'):
            entregas.compartir(self.profe.id_profesor, sin_nada.pk, self.videos[0])
        paquete = self.paquete(alumno=self.beto)
        self.extra(paquete, 1)
        self.compartir(paquete, 1)
        with self.assertRaises(ValidationError):
            entregas.compartir(self.profe.id_profesor, paquete.pk, self.videos[1])


class PlazoTests(Base):

    def test_un_extra_comprado_hoy_se_debe_en_14_dias(self):
        self.extra(self.paquete(), 2)
        fila = self.fila()
        self.assertEqual((fila['videos'], fila['falta'], fila['atrasada']), (2, 2, False))
        self.assertEqual(fila['proxima'], timezone.localtime(timezone.now() + timedelta(days=14)).strftime('%d-%m-%Y'))

    def test_pasados_los_14_dias_esta_atrasado(self):
        self.extra(self.paquete(), 2, pagada_hace=15)
        self.assertTrue(self.fila()['atrasada'])

    def test_el_extra_se_suma_a_lo_del_plan_con_su_propia_fecha(self):
        paquete = self.paquete(videos=1)  # el video del plan vencia el dia 14, hace 4 dias de vida: aun no
        self.extra(paquete, 1, pagada_hace=0)
        self.compartir(paquete, 1)
        fila = self.fila()
        self.assertEqual((fila['compartidos'], fila['videos'], fila['falta'], fila['atrasada']), (1, 2, 1, False))

    def test_un_extra_pendiente_no_corre_plazo(self):
        self.extra(self.paquete(videos=1), 2, estado=PENDIENTE)
        self.assertEqual(self.fila()['videos'], 1)

    def test_aviso_a_los_3_dias_y_ticket_si_se_atrasa(self):
        self.extra(self.paquete(), 2, pagada_hace=11)  # vence en 3 dias
        self.assertEqual(plazos_videos.revisar(), (1, 0))
        self.extra(self.paquete(alumno=self.beto), 1, pagada_hace=15)
        self.assertEqual(plazos_videos.revisar()[1], 1)
        self.assertTrue(Ticket.objects.filter(categoria=Ticket.VIDEOS, autor=self.profe.user).exists())


class SaldoTests(Base):

    def test_un_extra_sin_agregado_paga_el_75_de_lo_que_costo(self):
        paquete = self.paquete()
        self.extra(paquete, 3)  # $13.500: $4.500 por video
        self.compartir(paquete, 3)
        saldo = calcular_saldos(self.profe)
        self.assertEqual(saldo['total_ganado'], 13500)
        self.assertEqual(saldo['disponible'], 3 * paquetes.pago_profesor(4500, paquetes.COMISION_VIDEOS))

    def test_con_agregado_y_extra_el_valor_es_el_promedio(self):
        paquete = self.paquete(videos=1)  # $5.000
        self.extra(paquete, 3)  # $13.500: en total $18.500 por 4 videos
        self.compartir(paquete, 4)
        saldo = calcular_saldos(self.profe)
        self.assertEqual(saldo['total_ganado'], 18500)
        self.assertEqual(saldo['disponible'], 4 * paquetes.pago_profesor(18500 // 4, paquetes.COMISION_VIDEOS))

    def test_un_extra_pendiente_no_cambia_el_valor(self):
        paquete = self.paquete(videos=1)
        self.extra(paquete, 3, estado=PENDIENTE)
        self.compartir(paquete, 1)
        self.assertEqual(calcular_saldos(self.profe)['total_ganado'], 5000)


class AvisoTests(Base):

    def respuesta(self, compra, **cambios):
        return {'response_code': 0, 'status': 'AUTHORIZED', 'buy_order': compra.buy_order, 'amount': compra.monto,
                'authorization_code': '1213', **cambios}

    def pendiente(self):
        return self.extra(self.paquete(), 3, estado=PENDIENTE)

    def avisos(self):
        return list(Notificacion.objects.filter(usuario=self.profe.user).values_list('texto', flat=True))

    def test_al_confirmarse_el_pago_se_avisa_al_profesor_una_sola_vez(self):
        compra = self.pendiente()
        with self.captureOnCommitCallbacks(execute=True):
            registrar_respuesta(self.respuesta(compra))
            registrar_respuesta(self.respuesta(compra))  # el retorno de Webpay puede llegar dos veces
        [aviso] = self.avisos()
        self.assertIn('Ana', aviso)
        self.assertIn('3 videos', aviso)
        self.assertIn(timezone.localtime(timezone.now() + timedelta(days=14)).strftime('%d/%m/%Y'), aviso)
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.profe.user.email])

    def test_un_pago_rechazado_no_avisa(self):
        compra = self.pendiente()
        with self.captureOnCommitCallbacks(execute=True):
            registrar_respuesta(self.respuesta(compra, response_code=-1))
        self.assertEqual((self.avisos(), len(mail.outbox)), ([], 0))

    def test_si_el_aviso_falla_el_pago_igual_queda_confirmado(self):
        compra = self.pendiente()
        with mock.patch('alumnos.avisos_profesor.videos_extra_comprados', side_effect=RuntimeError('smtp')), \
                self.assertLogs('alumnos.webpay', 'ERROR'), self.captureOnCommitCallbacks(execute=True):
            registrar_respuesta(self.respuesta(compra))
        compra.refresh_from_db()
        self.assertEqual(compra.estado, ACTIVA)
