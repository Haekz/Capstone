"""Planes reales: Suscripcion como unica fuente de verdad del plan del alumno.

- Al iniciar Webpay (alumna logueada) se crean suscripciones pendientes.
- Solo un commit aprobado de Transbank las activa (buscando por buy_order,
  sin depender de la cookie de sesion) y es idempotente.
- El portal lee el plan del servidor: nada de localStorage ni pagos simulados,
  y el contenido premium no llega al HTML sin plan premium.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, Suscripcion

User = get_user_model()

RUT = '11111111-1'
CLAVE = 'Clave12345!'


def dar_plan(alumno, plan='2', dias=30, buy_order='LB0000001'):
    """Suscripcion activa y vigente, como si Webpay hubiera aprobado el pago."""
    return Suscripcion.objects.create(
        alumno=alumno, plan=plan, dias=dias, monto=139990, buy_order=buy_order,
        estado=Suscripcion.ESTADO_ACTIVA, fecha_fin=timezone.now() + timedelta(days=dias),
    )


def mock_transbank(mock_tx, **commit):
    instancia = MagicMock()
    instancia.create.return_value = {'url': 'https://webpay.test', 'token': 'tok'}
    instancia.commit.return_value = commit
    mock_tx.return_value = instancia
    return instancia


class SuscripcionModeloTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(RUT, rut=RUT, password=CLAVE, rol='alumno')
        cls.alumno = Alumno.objects.create(user=user, nivel_educacion='media')

    def _pendiente(self, buy_order='LB1', plan='2', dias=30):
        return Suscripcion.objects.create(alumno=self.alumno, plan=plan, dias=dias,
                                          monto=139990, buy_order=buy_order)

    def test_pago_aprobado_activa_solo_las_pendientes_de_esa_orden(self):
        propia, otra = self._pendiente('LB1', dias=14), self._pendiente('LB2')
        Suscripcion.confirmar_pago('LB1', aprobado=True)
        propia.refresh_from_db()
        otra.refresh_from_db()
        self.assertEqual(propia.estado, Suscripcion.ESTADO_ACTIVA)
        self.assertAlmostEqual(propia.fecha_fin, timezone.now() + timedelta(days=14),
                               delta=timedelta(minutes=1))
        self.assertEqual(otra.estado, Suscripcion.ESTADO_PENDIENTE)

    def test_pago_rechazado_no_da_plan(self):
        s = self._pendiente()
        Suscripcion.confirmar_pago('LB1', aprobado=False)
        s.refresh_from_db()
        self.assertEqual(s.estado, Suscripcion.ESTADO_RECHAZADA)
        self.assertIsNone(self.alumno.plan_vigente())

    def test_confirmar_dos_veces_es_idempotente(self):
        s = self._pendiente()
        Suscripcion.confirmar_pago('LB1', aprobado=True)
        s.refresh_from_db()
        fin = s.fecha_fin
        Suscripcion.confirmar_pago('LB1', aprobado=True)
        Suscripcion.confirmar_pago('LB1', aprobado=False)  # no revierte una ya activa
        s.refresh_from_db()
        self.assertEqual((s.estado, s.fecha_fin), (Suscripcion.ESTADO_ACTIVA, fin))

    def test_plan_vigente(self):
        self.assertIsNone(self.alumno.plan_vigente())
        vencida = dar_plan(self.alumno, buy_order='LB-vieja')
        vencida.fecha_fin = timezone.now() - timedelta(days=1)
        vencida.save()
        self.assertIsNone(self.alumno.plan_vigente())
        basico = dar_plan(self.alumno, plan=Suscripcion.PLAN_BASICO, buy_order='LB-basico')
        self.assertEqual(self.alumno.plan_vigente(), basico)
        self.assertFalse(basico.es_premium)
        self.assertTrue(dar_plan(self.alumno, plan='3', dias=60).es_premium)


class FlujoWebpayTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(RUT, rut=RUT, password=CLAVE, rol='alumno')
        cls.alumno = Alumno.objects.create(user=user, nivel_educacion='media')

    # La compra con carrito (iniciar_webpay) ya no existe: ver tests/test_paquetes.py.
    # Estas suscripciones son las de antes de los paquetes; siguen valiendo hasta vencer.

    @patch('alumnos.views._tx')
    def test_confirmacion_activa_aunque_vuelva_sin_cookie_de_sesion(self, mock_tx):
        Suscripcion.objects.create(alumno=self.alumno, plan='2', dias=30,
                                   monto=139990, buy_order='LB777')
        mock_transbank(mock_tx, response_code=0, status='AUTHORIZED', buy_order='LB777',
                       amount=139990)
        r = Client().post(reverse('confirmacion'), {'token_ws': 'tok'})  # cliente sin sesion
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.alumno.plan_vigente().buy_order, 'LB777')

    @patch('alumnos.views._tx')
    def test_confirmacion_rechazada_no_activa(self, mock_tx):
        Suscripcion.objects.create(alumno=self.alumno, plan='2', dias=30,
                                   monto=139990, buy_order='LB888')
        mock_transbank(mock_tx, response_code=-1, status='FAILED', buy_order='LB888')
        Client().post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertIsNone(self.alumno.plan_vigente())
        self.assertEqual(Suscripcion.objects.get().estado, Suscripcion.ESTADO_RECHAZADA)


class PortalPlanTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        user = User.objects.create_user(RUT, rut=RUT, password=CLAVE, rol='alumno')
        cls.alumno = Alumno.objects.create(user=user, nivel_educacion='media')

    def _portal(self):
        self.client.post(reverse('login'), {'username': RUT, 'password': CLAVE})
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.status_code, 200)
        return r

    def assertContenidoPremium(self, respuesta, visible):
        for marca in ('id="chat-msg-input"', 'id="progress-stat-hours"'):
            (self.assertContains if visible else self.assertNotContains)(respuesta, marca)

    def test_sin_plan(self):
        r = self._portal()
        self.assertContains(r, '<script id="plan-activo" type="application/json">null</script>')
        self.assertContenidoPremium(r, visible=False)
        self.assertContains(r, 'Aún no tienes pagos registrados.')

    def test_plan_basico_no_desbloquea_premium(self):
        dar_plan(self.alumno, plan=Suscripcion.PLAN_BASICO)
        r = self._portal()
        self.assertEqual(r.context['plan_activo'], {'nombre': 'Plan Básico', 'premium': False})
        self.assertContenidoPremium(r, visible=False)

    def test_plan_premium_desbloquea_y_aparece_en_historial(self):
        dar_plan(self.alumno, plan='2', buy_order='LB4242')
        r = self._portal()
        self.assertEqual(r.context['plan_activo'], {'nombre': 'Plan Medio', 'premium': True})
        self.assertContenidoPremium(r, visible=True)
        self.assertContains(r, '<code>LB4242</code>')
        self.assertContains(r, '<td>$139.990</td>', html=True)  # formato chileno
        self.assertContains(r, f'<td>{timezone.localdate():%d-%m-%Y}</td>', html=True)
        self.assertContains(r, '<span class="tx-badge success">Aprobado</span>', html=True)

    def test_sin_plan_simulado_ni_localstorage(self):
        r = self._portal()
        for simulado in ("localStorage.getItem('hasPlan')", "localStorage.setItem('hasPlan'",
                         'TX-99812', 'Conectándote con Transbank Webpay'):
            self.assertNotContains(r, simulado)


class SoportePagosTests(TestCase):

    def test_admin_encuentra_suscripciones_por_buy_order(self):
        user = User.objects.create_user(RUT, rut=RUT, password=CLAVE, rol='alumno')
        dar_plan(Alumno.objects.create(user=user, nivel_educacion='media'), buy_order='LB-SOPORTE')
        self.client.force_login(User.objects.create_superuser('admin', 'a@lbwus.cl', CLAVE))
        r = self.client.get(reverse('admin:alumnos_suscripcion_changelist'), {'q': 'LB-SOPORTE'})
        self.assertContains(r, 'LB-SOPORTE')
