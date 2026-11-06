"""Revision QA: pagos con Webpay (alumnos/views.py: comprar_paquete, iniciar_compra_paquete, confirmacion).

Complementa tests/test_paquetes.py (precio del servidor, monto menor, orden
unica, replay, TBK_TOKEN). Cada prueba nombra el riesgo que cubre. Webpay va
con mock: ninguna prueba llama a Transbank.
"""

from unittest.mock import patch

from django.test import Client
from django.urls import reverse

from alumnos.models import PaqueteClases
from tests.bugs_qa import bug_qa
from tests.test_paquetes import RUT_ANA, Escenario

APROBADO = {'response_code': 0, 'status': 'AUTHORIZED'}


@patch('alumnos.webpay._tx')
class ConfirmacionQATests(Escenario):

    def comprar(self, mock_tx, plan='progreso'):
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        self.client.post(reverse('comprar_paquete'), {'plan': plan, 'profesor': self.profe.id_profesor})
        return PaqueteClases.objects.get()

    def volver_de_webpay(self, mock_tx, paquete, client=None, **respuesta):
        mock_tx.return_value.commit.return_value = {'amount': paquete.monto, 'buy_order': paquete.buy_order,
                                                    **APROBADO, **respuesta}
        return (client or self.client).post(reverse('confirmacion'), {'token_ws': 'tok'})

    def estado(self, paquete):
        paquete.refresh_from_db()
        return paquete.estado

    def test_solo_activa_con_codigo_0_y_estado_authorized_a_la_vez(self, mock_tx):
        """Riesgo: activar clases con un pago que Transbank no autorizo (basta que falle uno de los dos)."""
        paquete = self.comprar(mock_tx)
        for codigo, estado in ((0, 'FAILED'), (0, 'REVERSED'), (-1, 'AUTHORIZED'), (None, 'AUTHORIZED'),
                               ('0', 'AUTHORIZED'), (0, None)):
            with self.subTest(response_code=codigo, status=estado):
                PaqueteClases.objects.filter(pk=paquete.pk).update(estado=PaqueteClases.ESTADO_PENDIENTE)
                r = self.volver_de_webpay(mock_tx, paquete, response_code=codigo, status=estado)
                self.assertContains(r, 'Pago Rechazado')
                self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)

    def test_monto_mayor_al_del_paquete_tambien_se_rechaza(self, mock_tx):
        """Riesgo: monto manipulado hacia arriba (test_paquetes prueba solo uno menor)."""
        paquete = self.comprar(mock_tx)
        self.volver_de_webpay(mock_tx, paquete, amount=paquete.monto + 1)
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)

    def test_respuesta_sin_monto_se_rechaza(self, mock_tx):
        """Riesgo: una respuesta incompleta (sin amount) no puede valer como pago completo."""
        paquete = self.comprar(mock_tx)
        self.client.raise_request_exception = False  # la pagina da 500: BUG-QA-05, abajo
        self.volver_de_webpay(mock_tx, paquete, amount=None)
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)

    @bug_qa('BUG-QA-05', 'con amount=None la pagina de confirmacion da 500 (filtro dinero: int(None))')
    def test_respuesta_sin_monto_muestra_el_rechazo_sin_error(self, mock_tx):
        """Riesgo: el alumno vuelve de Webpay a una pagina de error en vez del aviso de pago rechazado."""
        paquete = self.comprar(mock_tx)
        self.client.raise_request_exception = False
        r = self.volver_de_webpay(mock_tx, paquete, amount=None)
        self.assertContains(r, 'Pago Rechazado')

    def test_un_paquete_rechazado_no_se_reactiva_con_un_retorno_aprobado_posterior(self, mock_tx):
        """Riesgo: replay de un retorno aprobado sobre una orden ya rechazada da clases gratis."""
        paquete = self.comprar(mock_tx)
        self.volver_de_webpay(mock_tx, paquete, response_code=-1, status='FAILED')
        self.volver_de_webpay(mock_tx, paquete)
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_RECHAZADA)
        self.assertEqual(self.ana.paquetes.vigentes().count(), 0)

    def test_un_paquete_activo_no_extiende_su_vigencia_con_un_replay(self, mock_tx):
        """Riesgo: repetir el retorno aprobado reinicia la vigencia (fecha_fin) del paquete."""
        paquete = self.comprar(mock_tx)
        self.volver_de_webpay(mock_tx, paquete)
        paquete.refresh_from_db()
        fin = paquete.fecha_fin
        self.volver_de_webpay(mock_tx, paquete)
        paquete.refresh_from_db()
        self.assertEqual(paquete.fecha_fin, fin)

    def test_el_retorno_sin_cookie_de_sesion_igual_confirma_por_la_orden(self, mock_tx):
        """Riesgo: Webpay vuelve en otra pestana o sin cookie: el pago se confirma por buy_order, no por sesion."""
        paquete = self.comprar(mock_tx)
        self.volver_de_webpay(mock_tx, paquete, client=Client())
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_ACTIVA)

    @bug_qa('BUG-QA-02', 'confirmacion llama a commit() aunque lleguen token_ws y TBK_TOKEN juntos')
    def test_token_ws_y_tbk_token_juntos_no_confirman(self, mock_tx):
        """Riesgo: Transbank manda los dos cuando el pago es invalido (error en el formulario y vuelta al
        comercio); su guia dice no confirmarlo. Hoy se llama a commit() igual: con un commit que
        responde aprobado, el paquete se activa."""
        paquete = self.comprar(mock_tx)
        mock_tx.return_value.commit.return_value = {'amount': paquete.monto, 'buy_order': paquete.buy_order,
                                                    **APROBADO}
        self.client.post(reverse('confirmacion'), {'token_ws': 'tok', 'TBK_TOKEN': 'tok'})
        mock_tx.return_value.commit.assert_not_called()
        self.assertEqual(self.estado(paquete), PaqueteClases.ESTADO_PENDIENTE)


@patch('alumnos.webpay._tx')
class CompraCsrfTests(Escenario):

    def test_comprar_exige_el_token_csrf(self, mock_tx):
        """Riesgo: un sitio ajeno inicia una compra en nombre del alumno con sesion abierta (regla 4)."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.ana.user)
        sesion = client.session
        sesion['alumno_id'] = self.ana.id_alumno
        sesion.save()
        r = client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        self.assertEqual(r.status_code, 403)
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())

    def test_confirmacion_no_exige_csrf_porque_la_llama_transbank(self, mock_tx):
        """El unico @csrf_exempt del proyecto: Transbank hace el POST de vuelta sin el token del sitio."""
        mock_tx.return_value.commit.side_effect = Exception('token invalido')
        r = Client(enforce_csrf_checks=True).post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertEqual(r.status_code, 200)


class PlanesJsonTests(Escenario):

    @bug_qa('BUG-QA-01', 'planes?format=json devuelve precios fijos de la tarifa base, no los del profesor')
    def test_el_json_de_planes_usa_la_tarifa_del_profesor(self):
        """Riesgo: lo que muestra el sitio no es lo que se cobra (planes: 'todo precio sale de paquetes.py')."""
        self.profe.tarifa = 20000
        self.profe.save()
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor, 'format': 'json'})
        self.assertEqual([p['precio_total'] for p in r.json()['planes']], [20000, 79000, 155000])
