"""Recordatorio a los lideres por requerimientos de autoridad por vencer o atrasados. Datos ficticios."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from requerimientos import avisos, gestion
from tests.test_apoderados import crear_agente
from tests.test_mensajes_revision_avisos import dia_habil

AUTORIDAD, REFERENCIA = 'Fiscalía Local de Providencia', 'RUC 2600123456-7'
COMANDO = 'requerimientos.management.commands.avisar_requerimientos_por_vencer.es_habil'


class AvisosRequerimientosTests(TestCase):

    def setUp(self):
        self.hoy = timezone.localdate()
        self.lider = crear_agente('10000002-7', lider=True)
        self.agente = crear_agente('10000001-9')

    def registrar(self, vence):
        return gestion.registrar(self.lider, AUTORIDAD, REFERENCIA, self.hoy - timedelta(days=30),
                                 'Pagos del ticket 123.', vence=vence)

    def test_avisa_desde_3_dias_habiles_antes_del_plazo(self):
        self.registrar(dia_habil(self.hoy, 3))
        self.assertEqual(avisos.avisar(self.hoy), 1)
        [correo] = mail.outbox
        self.assertEqual(correo.to, [self.lider.user.email])  # solo al lider, no al agente
        self.assertIn('Requerimientos de autoridad por vencer', correo.subject)
        self.assertIn('Hay 1 requerimiento de autoridad que vence en los próximos 3 días hábiles', correo.body)

    def test_con_4_dias_habiles_por_delante_todavia_no_avisa(self):
        self.registrar(dia_habil(self.hoy, 4))
        self.assertEqual(avisos.avisar(self.hoy), 0)
        self.assertEqual(mail.outbox, [])

    def test_el_dia_del_plazo_avisa(self):
        self.registrar(self.hoy)
        self.assertEqual(avisos.contar(self.hoy), (1, 0))

    def test_atrasado_avisa_como_vencido(self):
        self.registrar(self.hoy - timedelta(days=1))
        self.assertEqual(avisos.avisar(self.hoy), 1)
        self.assertIn('1 requerimiento de autoridad con el plazo vencido', mail.outbox[0].body)
        self.assertNotIn('que vence', mail.outbox[0].body)

    def test_cuenta_por_separado_y_en_plural(self):
        for _ in range(2):
            self.registrar(self.hoy - timedelta(days=1))
        self.registrar(self.hoy)
        self.assertEqual(avisos.avisar(self.hoy), 3)
        cuerpo = mail.outbox[0].body
        self.assertIn('Hay 2 requerimientos de autoridad con el plazo vencido', cuerpo)
        self.assertIn('Hay 1 requerimiento de autoridad que vence', cuerpo)

    def test_sin_plazo_no_avisa(self):
        self.registrar(None)
        self.assertEqual(avisos.avisar(self.hoy), 0)

    def test_rechazado_o_cerrado_no_avisa(self):
        gestion.rechazar(self.lider, self.registrar(self.hoy), 'No se pudo verificar.')
        verificado = gestion.verificar(self.lider, self.registrar(self.hoy), 'Confirmado por teléfono.')
        gestion.cerrar(self.lider, verificado, 'Se respondió el oficio.')
        self.assertEqual(avisos.avisar(self.hoy), 0)

    def test_verificado_sigue_abierto_y_avisa(self):
        gestion.verificar(self.lider, self.registrar(self.hoy), 'Confirmado por teléfono.')
        self.assertEqual(avisos.contar(self.hoy), (1, 0))

    def test_el_correo_no_lleva_la_autoridad_ni_la_referencia(self):
        self.registrar(self.hoy)
        avisos.avisar(self.hoy)
        for detalle in (AUTORIDAD, REFERENCIA, 'ticket 123'):
            self.assertNotIn(detalle, mail.outbox[0].body)

    # --- comando ---

    def test_el_comando_no_envia_en_dias_no_habiles(self):
        self.registrar(self.hoy)
        salida = StringIO()
        with patch(COMANDO, return_value=False):
            call_command('avisar_requerimientos_por_vencer', stdout=salida)
        self.assertIn('no es día hábil', salida.getvalue())
        self.assertEqual(mail.outbox, [])

    def test_el_comando_informa_solo_la_cantidad(self):
        self.registrar(self.hoy)
        salida = StringIO()
        with patch(COMANDO, return_value=True):
            call_command('avisar_requerimientos_por_vencer', stdout=salida)
        self.assertEqual(salida.getvalue().strip(), 'Requerimientos por vencer o atrasados avisados: 1')
        self.assertEqual(len(mail.outbox), 1)
