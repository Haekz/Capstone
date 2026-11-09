"""Aviso al profesor cuando le compran el agregado de videos (fase 3c).

Sale una sola vez, en el momento en que el paquete pasa de pendiente a activo (por el retorno de Webpay o por la
revision automatica de pagos pendientes: ambos pasan por registrar_respuesta). Lleva cuantos videos, las fechas limite
y las reglas. Del alumno, solo el nombre de pila. Un fallo al avisar nunca debe tumbar la confirmacion del pago.
"""

from datetime import timedelta
from unittest import mock

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.webpay import registrar_respuesta
from notificaciones.models import Notificacion
from tests.test_agregado_videos import respuesta_webpay
from tests.test_paquetes import RUT_ANA, Escenario


class AvisoAgregadoTests(Escenario):

    def pendiente(self, plan='progreso', videos=4, profesor=True):
        return PaqueteClases.objects.create(
            alumno=self.ana, profesor=self.profe if profesor else None, plan=plan, clases=4, tarifa=15000, monto=59000,
            videos=videos, monto_videos=videos * paquetes.PRECIO_VIDEO, dias=paquetes.POR_CODIGO[plan].vigencia_dias,
            buy_order=f'PQ{PaqueteClases.objects.count():024d}', estado=PaqueteClases.ESTADO_PENDIENTE)

    def pagar(self, paquete, monto=None):
        """El retorno de Webpay, con los avisos on_commit ejecutados (TestCase no los ejecuta solo)."""
        with self.captureOnCommitCallbacks(execute=True):
            return registrar_respuesta(respuesta_webpay(paquete, monto if monto is not None else paquete.total))

    def campanitas(self):
        return Notificacion.objects.filter(usuario=self.profe.user)

    def test_avisa_con_cuantos_videos_las_fechas_y_las_reglas(self):
        paquete = self.pendiente()
        self.assertTrue(self.pagar(paquete)[0])
        paquete.refresh_from_db()
        [campanita] = self.campanitas()
        self.assertIn('Ana contrató 4 videos de apoyo', campanita.texto)
        self.assertEqual(campanita.enlace, reverse('panel_profesor'))
        [correo] = mail.outbox
        self.assertEqual((correo.to, correo.subject), ([self.profe.user.email], 'Nuevo agregado de videos - LBWUS'))
        self.assertIn('Ana contrató 4 videos de apoyo', correo.body)
        inicio = paquete.fecha_fin - timedelta(days=paquete.dias)
        for fecha, acumulado in paquetes.fechas_entrega(paquetes.POR_CODIGO['progreso'], inicio):
            self.assertIn(f'el {timezone.localtime(fecha):%d/%m/%Y} ({acumulado} en total)', correo.body)
        for regla in ('pestaña Videos', 'mismo video', 'vigente'):
            self.assertIn(regla, correo.body)

    def test_no_entrega_datos_del_alumno_mas_que_el_nombre_de_pila(self):
        self.pagar(self.pendiente())
        textos = mail.outbox[0].body + self.campanitas()[0].texto
        for dato in (RUT_ANA, self.ana.user.email):
            self.assertNotIn(dato, textos)

    def test_un_video_va_en_singular_y_cada_plan_trae_sus_fechas(self):
        for plan, videos, fechas in (('flexible', 1, 1), ('progreso', 4, 2), ('intensivo', 6, 3)):
            with self.subTest(plan=plan):
                mail.outbox.clear()
                self.pagar(self.pendiente(plan, videos))
                cuerpo = mail.outbox[0].body
                self.assertIn(f'contrató {videos} video{"" if videos == 1 else "s"} de apoyo', cuerpo)
                self.assertEqual(cuerpo.count(' en total)'), fechas)

    def test_sale_una_sola_vez_aunque_webpay_vuelva_dos_veces(self):
        paquete = self.pendiente()
        self.pagar(paquete)
        self.pagar(paquete)  # el retorno del alumno y la revisión automática pueden coincidir
        self.assertEqual((self.campanitas().count(), len(mail.outbox)), (1, 1))

    def test_no_avisa_si_el_pago_no_se_aprueba_ni_si_no_hay_videos(self):
        self.assertFalse(self.pagar(self.pendiente(), monto=1)[0])  # Transbank cobró otro monto: rechazada
        self.pagar(self.pendiente(videos=0))
        self.assertEqual((self.campanitas().count(), len(mail.outbox)), (0, 0))

    def test_sin_profesor_no_se_cae(self):
        paquete = self.pendiente(profesor=False)
        self.assertTrue(self.pagar(paquete)[0])
        self.assertEqual(len(mail.outbox), 0)

    def test_si_falla_el_aviso_el_pago_igual_queda_confirmado(self):
        paquete = self.pendiente()
        with mock.patch('alumnos.avisos_profesor.agregado_videos', side_effect=RuntimeError('correo caído')):
            with self.assertLogs('alumnos.webpay', 'ERROR'):
                self.assertTrue(self.pagar(paquete)[0])
        paquete.refresh_from_db()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)
