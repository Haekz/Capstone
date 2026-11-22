"""SCRUM-100: logging, monitoreo y alertas.

- tareas_diarias: si una tarea falla, log ERROR, correo a ALERTAS_CORREOS y el comando termina con error.
- /salud/: 200 si la ultima corrida completa fue hace menos de 26 h; 503 si no o si nunca corrio.
- Aviso en el panel admin cuando las tareas estan atrasadas.
- Los logs de login y de pago no llevan la contrasena, el token ni el RUT completo.
Webpay va con mock: ninguna prueba llama a Transbank. El correo usa el backend en memoria de las pruebas.
"""

import json
import logging
from datetime import timedelta
from io import StringIO
from smtplib import SMTPException
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos.management.commands.tareas_diarias import TAREAS
from alumnos.models import PaqueteClases, Tutor
from lbwus import salud
from lbwus.registro import FormatoSeguro, enmascarar_token, enmascarar_usuario, limpiar
from tests.test_paquetes import RUT_ANA, Escenario

LLAMAR = 'alumnos.management.commands.tareas_diarias.call_command'
LOG_TAREAS = 'alumnos.management.commands.tareas_diarias'
EQUIPO = ['equipo@lbwus.test', 'qa@lbwus.test']
TOKEN = 'e9' * 32  # 64 hexadecimales, como un token real de Webpay
CLAVE_ESCRITA = 'MiClaveSecreta#2026'


def _fallando(*caidas):
    def llamar(nombre, **kwargs):
        if nombre in caidas:
            raise RuntimeError('detalle interno de la caida con rut 12.345.678-5')
    return llamar


class AlertaTareasDiariasTests(TestCase):

    def setUp(self):
        cache.clear()

    @override_settings(ALERTAS_CORREOS=EQUIPO)
    def test_una_tarea_que_falla_deja_log_error_avisa_por_correo_y_termina_con_error(self):
        with mock.patch(LLAMAR, side_effect=_fallando('revisar_pagos_pendientes', 'avisar_entregas_videos')), \
                self.assertLogs(LOG_TAREAS, 'ERROR') as logs, \
                self.assertRaisesMessage(CommandError, f'Fallaron 2 de {len(TAREAS)}'):
            call_command('tareas_diarias', stdout=StringIO())

        self.assertTrue(any('evento=tarea_diaria_fallida tarea=revisar_pagos_pendientes' in linea
                            for linea in logs.output))
        self.assertTrue(any('evento=tareas_diarias_con_error' in linea for linea in logs.output))
        self.assertEqual(len(mail.outbox), 1)
        correo = mail.outbox[0]
        self.assertEqual(correo.to, EQUIPO)
        self.assertIn(f'Fallaron 2 de {len(TAREAS)} tareas diarias', correo.subject)
        self.assertIn('- revisar_pagos_pendientes', correo.body)
        self.assertIn('- avisar_entregas_videos', correo.body)
        self.assertIn(timezone.localtime().strftime('%d-%m-%Y'), correo.body)  # la hora de la corrida
        # Sin trazas ni datos: el detalle queda solo en el log.
        for texto in ('Traceback', 'RuntimeError', 'detalle interno', '12.345.678-5', 'generar_bloques'):
            self.assertNotIn(texto, correo.body)

    @override_settings(ALERTAS_CORREOS=EQUIPO)
    def test_una_corrida_con_error_no_cuenta_como_corrida_completa(self):
        with mock.patch(LLAMAR, side_effect=_fallando('generar_bloques')), self.assertLogs(LOG_TAREAS, 'ERROR'), \
                self.assertRaises(CommandError):
            call_command('tareas_diarias', stdout=StringIO())
        self.assertIsNone(salud.ultima_corrida())

    @override_settings(ALERTAS_CORREOS=[])
    def test_sin_alertas_correos_no_se_envia_nada_y_el_comando_igual_falla(self):
        with mock.patch(LLAMAR, side_effect=_fallando('generar_bloques')), \
                self.assertLogs('lbwus.alertas', 'WARNING') as logs, \
                self.assertLogs(LOG_TAREAS, 'ERROR'), self.assertRaises(CommandError):
            call_command('tareas_diarias', stdout=StringIO())
        self.assertEqual(mail.outbox, [])
        self.assertIn('evento=alerta_omitida', logs.output[0])

    @override_settings(ALERTAS_CORREOS=EQUIPO)
    def test_si_el_correo_no_sale_el_comando_igual_termina_con_error(self):
        with mock.patch(LLAMAR, side_effect=_fallando('generar_bloques')), \
                mock.patch('lbwus.alertas.send_mail', side_effect=SMTPException('smtp caido')), \
                self.assertLogs('lbwus.alertas', 'ERROR') as logs, self.assertLogs(LOG_TAREAS, 'ERROR'), \
                self.assertRaisesMessage(CommandError, 'generar_bloques'):
            call_command('tareas_diarias', stdout=StringIO())
        self.assertIn('evento=alerta_no_enviada error=SMTPException', logs.output[0])

    @override_settings(ALERTAS_CORREOS=EQUIPO)
    def test_una_corrida_completa_no_avisa_y_guarda_la_hora(self):
        with mock.patch(LLAMAR):
            call_command('tareas_diarias', stdout=StringIO())
        self.assertEqual(mail.outbox, [])
        self.assertLess(timezone.now() - salud.ultima_corrida(), timedelta(minutes=1))


class SaludTests(TestCase):

    def setUp(self):
        cache.clear()

    def consultar(self, metodo='get'):
        return getattr(self.client, metodo)(reverse('salud'))

    def test_url(self):
        self.assertEqual(reverse('salud'), '/salud/')

    def test_si_nunca_corrio_da_503_atrasado(self):
        r = self.consultar()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(json.loads(r.content), {'estado': 'atrasado'})

    def test_tras_una_corrida_completa_da_200_ok(self):
        with mock.patch(LLAMAR):
            call_command('tareas_diarias', stdout=StringIO())
        r = self.consultar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content), {'estado': 'ok'})  # ningun otro dato interno

    def test_con_25_horas_sigue_ok(self):
        salud.marcar_corrida(timezone.now() - timedelta(hours=25))
        self.assertEqual(self.consultar().status_code, 200)

    def test_con_mas_de_26_horas_da_503_atrasado(self):
        salud.marcar_corrida(timezone.now() - timedelta(hours=26, minutes=1))
        r = self.consultar()
        self.assertEqual(r.status_code, 503)
        self.assertEqual(json.loads(r.content), {'estado': 'atrasado'})

    def test_si_la_cache_no_responde_da_503_y_no_500(self):
        with mock.patch.object(salud.cache, 'get', side_effect=RuntimeError('base caida')), \
                self.assertLogs('lbwus.salud', 'ERROR'):
            self.assertEqual(self.consultar().status_code, 503)

    def test_responde_a_head_para_los_monitores_y_no_a_post(self):
        salud.marcar_corrida()
        self.assertEqual(self.consultar('head').status_code, 200)
        self.assertEqual(self.consultar('post').status_code, 405)

    def test_no_se_guarda_en_cache_del_navegador_ni_de_proxies(self):
        self.assertIn('no-cache', self.consultar()['Cache-Control'])

    @override_settings(SITIO_CLAVE='clave-de-la-puerta-de-prueba')
    def test_la_puerta_del_sitio_no_la_bloquea(self):
        salud.marcar_corrida()
        r = self.consultar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.content), {'estado': 'ok'})

    def test_no_pide_login_ni_redirige(self):
        """Sin sesion: responde ella misma, nunca un 302 al login."""
        self.assertNotIn(self.consultar().status_code, (301, 302))


class AvisoAdminTests(TestCase):
    RUT = '44444444-4'
    CLAVE = 'AdminPassword123!'

    @classmethod
    def setUpTestData(cls):
        user = get_user_model().objects.create_user(
            username=cls.RUT, rut=cls.RUT, password=cls.CLAVE, rol='admin', first_name='Admin')
        Tutor.objects.create(user=user)

    def setUp(self):
        cache.clear()
        self.client.post(reverse('login'), {'username': self.RUT, 'password': self.CLAVE})

    def test_avisa_cuando_las_tareas_estan_atrasadas(self):
        r = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Las tareas diarias están atrasadas')
        self.assertContains(r, 'class="aviso-tareas" role="alert"')

    def test_no_avisa_si_corrieron_hace_poco(self):
        salud.marcar_corrida()
        r = self.client.get(reverse('dashboard_admin'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Las tareas diarias están atrasadas')


class LogsDeLoginTests(TestCase):

    def setUp(self):
        cache.clear()

    def intentar(self, usuario, clave=CLAVE_ESCRITA):
        return self.client.post(reverse('login'), {'username': usuario, 'password': clave})

    def test_login_fallido_registra_usuario_enmascarado_e_ip_sin_la_clave_ni_el_rut(self):
        with self.assertLogs('alumnos.views', 'WARNING') as logs:
            self.intentar('12.345.678-5')
        salida = '\n'.join(logs.output)
        self.assertIn('evento=login_fallido', salida)
        self.assertIn('usuario=***678-5', salida)
        self.assertIn('ip=127.0.0.1', salida)
        for prohibido in (CLAVE_ESCRITA, '12.345.678', '12345678'):
            self.assertNotIn(prohibido, salida)

    def test_con_correo_no_queda_el_correo_completo(self):
        with self.assertLogs('alumnos.views', 'WARNING') as logs:
            self.intentar('juan.perez@gmail.com')
        salida = '\n'.join(logs.output)
        self.assertIn('usuario=j***@gmail.com', salida)
        self.assertNotIn('juan.perez', salida)
        self.assertNotIn(CLAVE_ESCRITA, salida)

    def test_el_bloqueo_por_intentos_queda_registrado_sin_la_clave(self):
        with self.assertLogs('alumnos.views', 'WARNING') as logs:
            for _ in range(6):  # 5 fallos activan el bloqueo; el sexto intento ya llega bloqueado
                self.intentar('12345678-5')
        salida = '\n'.join(logs.output)
        self.assertEqual(salida.count('evento=login_fallido'), 5)
        self.assertEqual(salida.count('evento=login_bloqueo_activado'), 1)
        self.assertEqual(salida.count('evento=login_bloqueado'), 1)
        self.assertNotIn(CLAVE_ESCRITA, salida)
        self.assertNotIn('12345678', salida)

    def test_las_distintas_formas_del_mismo_rut_comparten_la_referencia(self):
        with self.assertLogs('alumnos.views', 'WARNING') as logs:
            self.intentar('12.345.678-5')
            self.intentar('123456785')
        referencias = {linea.split('ref=')[1].split()[0] for linea in logs.output}
        self.assertEqual(len(referencias), 1)

    def test_un_usuario_con_saltos_de_linea_no_inventa_lineas_de_log(self):
        with self.assertLogs('alumnos.views', 'WARNING') as logs:
            self.intentar('x@dominio.cl\nERROR evento=pago_aprobado')
        self.assertNotIn('\n', logs.output[0])


@mock.patch('alumnos.webpay._tx')
class LogsDePagoTests(Escenario):

    def comprar(self, mock_tx):
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': TOKEN}
        with self.assertLogs('alumnos.webpay', 'INFO') as logs:
            self.client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        return PaqueteClases.objects.get(), logs.output

    def volver(self, mock_tx, paquete, **respuesta):
        mock_tx.return_value.commit.return_value = {
            'amount': paquete.total, 'buy_order': paquete.buy_order, 'response_code': 0, 'status': 'AUTHORIZED',
            'authorization_code': '1213', 'card_detail': {'card_number': '6623'}, **respuesta}
        with self.assertLogs('alumnos.webpay', 'INFO') as logs:
            self.client.post(reverse('confirmacion'), {'token_ws': TOKEN})
        return logs.output

    def assertSinDatosSensibles(self, salida):
        salida = '\n'.join(salida)
        for prohibido in (TOKEN, RUT_ANA, '6623', 'card'):
            self.assertNotIn(prohibido, salida)

    def test_inicio_y_aprobacion_con_orden_monto_y_estado(self, mock_tx):
        paquete, inicio = self.comprar(mock_tx)
        self.assertIn(f'evento=pago_iniciado tipo=paquete buy_order={paquete.buy_order} monto={paquete.total}',
                      inicio[0])
        final = self.volver(mock_tx, paquete)
        self.assertIn(f'evento=pago_aprobado buy_order={paquete.buy_order} monto={paquete.total}', final[0])
        self.assertIn('estado=AUTHORIZED', final[0])
        self.assertIn('activados=1', final[0])  # se registra despues de activar el paquete
        self.assertSinDatosSensibles(inicio + final)

    def test_una_orden_que_no_es_nuestra_queda_como_advertencia(self, mock_tx):
        mock_tx.return_value.commit.return_value = {
            'amount': 1000, 'buy_order': 'PQ' + '0' * 24, 'response_code': 0, 'status': 'AUTHORIZED'}
        with self.assertLogs('alumnos.webpay', 'INFO') as logs:
            self.client.post(reverse('confirmacion'), {'token_ws': TOKEN})
        self.assertTrue(logs.output[0].startswith('WARNING:'))
        self.assertIn('motivo=orden_desconocida', logs.output[0])
        self.assertIn('activados=0', logs.output[0])

    def test_rechazo(self, mock_tx):
        paquete, _ = self.comprar(mock_tx)
        final = self.volver(mock_tx, paquete, response_code=-1, status='FAILED')
        self.assertIn(f'evento=pago_rechazado buy_order={paquete.buy_order}', final[0])
        self.assertIn('estado=FAILED', final[0])
        self.assertSinDatosSensibles(final)

    def test_monto_distinto_queda_como_advertencia(self, mock_tx):
        paquete, _ = self.comprar(mock_tx)
        final = self.volver(mock_tx, paquete, amount=1)
        self.assertTrue(final[0].startswith('WARNING:'))
        self.assertIn('evento=pago_rechazado', final[0])
        self.assertIn('motivo=monto_distinto', final[0])

    def test_anulado_en_webpay(self, mock_tx):
        paquete, _ = self.comprar(mock_tx)
        with self.assertLogs('alumnos.webpay', 'INFO') as logs:
            self.client.post(reverse('confirmacion'), {'TBK_TOKEN': TOKEN})
        self.assertIn(f'evento=pago_anulado buy_order={paquete.buy_order}', logs.output[0])
        self.assertSinDatosSensibles(logs.output)

    def test_error_de_conexion_al_confirmar(self, mock_tx):
        paquete, _ = self.comprar(mock_tx)
        mock_tx.return_value.commit.side_effect = ConnectionError(f'https://webpay3gint/transactions/{TOKEN}')
        with self.assertLogs('alumnos.webpay', 'ERROR') as logs:
            self.client.post(reverse('confirmacion'), {'token_ws': TOKEN})
        self.assertIn(f'evento=pago_error_transbank etapa=commit buy_order={paquete.buy_order}', logs.output[0])
        self.assertIn('error=ConnectionError', logs.output[0])
        self.assertSinDatosSensibles(logs.output)  # el texto del error traia el token en la URL

    def test_error_de_conexion_al_iniciar(self, mock_tx):
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.side_effect = ConnectionError('transbank caido')
        with self.assertLogs('alumnos.webpay', 'ERROR') as logs:
            self.client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        self.assertIn('evento=pago_error_transbank etapa=create buy_order=PQ', logs.output[0])
        self.assertIn('error=ConnectionError', logs.output[0])
        self.assertFalse(PaqueteClases.objects.exists())


class EnmascaradoTests(SimpleTestCase):

    def test_usuario(self):
        self.assertEqual(enmascarar_usuario('12.345.678-k'), '***678-K')
        self.assertEqual(enmascarar_usuario('7654321-0'), '***321-0')
        self.assertEqual(enmascarar_usuario('ana.soto@duocuc.cl'), 'a***@duocuc.cl')
        self.assertEqual(enmascarar_usuario('administrador'), 'ad***')
        self.assertEqual(enmascarar_usuario(''), '-')

    def test_token(self):
        self.assertEqual(enmascarar_token(TOKEN), '...' + TOKEN[-6:])
        self.assertEqual(enmascarar_token(''), '-')

    def test_limpiar_cubre_errores_de_postgres_y_smtp(self):
        texto = limpiar('DETAIL: Key (rut)=(12345678-5) already exists. '
                        "{'ana.soto@duocuc.cl': (550, b'no existe')} token " + TOKEN)
        for prohibido in ('12345678-5', 'ana.soto', TOKEN):
            self.assertNotIn(prohibido, texto)
        self.assertIn('***678-5', texto)
        self.assertIn('a***@duocuc.cl', texto)

    def test_limpiar_oculta_la_clave_de_una_cadena_de_conexion(self):
        texto = limpiar('could not connect: postgresql://lbwus:ClaveDeLaBase99@db.interna:5432/lbwus')
        self.assertNotIn('ClaveDeLaBase99', texto)
        self.assertIn('postgresql://lbwus:***@db.interna:5432/lbwus', texto)

    def test_limpiar_no_toca_fechas_ordenes_ni_montos(self):
        texto = 'fecha=2026-11-20 buy_order=PQ0123456789abcdef01234567 monto=62990'
        self.assertEqual(limpiar(texto), texto)

    def test_el_formateador_de_la_consola_enmascara_tambien_las_trazas(self):
        try:
            raise ValueError('duplicado: 12.345.678-5 / ana.soto@duocuc.cl')
        except ValueError:
            registro = logging.LogRecord('x', logging.ERROR, __file__, 1, 'fallo %s', ('ana.soto@duocuc.cl',),
                                         exc_info=__import__('sys').exc_info())
        salida = FormatoSeguro('%(levelname)s %(name)s %(message)s').format(registro)
        self.assertIn('Traceback', salida)
        for prohibido in ('12.345.678-5', 'ana.soto'):
            self.assertNotIn(prohibido, salida)

    def test_la_consola_de_settings_usa_el_formateador_seguro(self):
        from django.conf import settings
        self.assertEqual(settings.LOGGING['formatters']['seguro']['()'], 'lbwus.registro.FormatoSeguro')
        self.assertEqual(settings.LOGGING['handlers']['consola']['formatter'], 'seguro')
        self.assertEqual(settings.LOGGING['loggers']['django.request']['level'], 'ERROR')
        self.assertEqual(settings.LOGGING['root']['level'], 'WARNING')
        self.assertEqual(settings.LOGGING['loggers']['alumnos']['level'], 'INFO')
