"""Paquetes de clases Flexible / Progreso / Intensivo (analisis de mercado 2.13-2.14, F-11).

Con la tarifa base de $15.000 por clase: $15.000 / $59.000 / $116.000, con una
comision de LBWUS del 15% (IVA incluido). Cubre precio, cantidad de clases,
compra, reserva, cancelacion, reprogramacion y permisos. Webpay va con mock.
"""

from datetime import time, timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes
from alumnos.exceptions import (
    CupoAgotadoError, InscripcionDuplicadaError, InscripcionError,
    SesionNoDisponibleError, SinClasesDisponiblesError,
)
from alumnos.models import (
    Asignatura, Clase, Especialidad, Genero, Inscripcion, PaqueteClases, Profesor, SesionClase,
)
from alumnos.services import InscripcionService
from tests.test_especialidad import CLAVE, crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_progreso_alumno import crear_alumno
from user_profesor.views import calcular_saldos

RUT_ANA, RUT_BETO = '11111111-1', '22222222-2'
RUT_PROFE, RUT_OTRO, RUT_SIN_TITULO = '33333333-3', '44444444-4', '55555555-5'


def dar_paquete(alumno, profesor, plan='progreso', dias=30, estado=PaqueteClases.ESTADO_ACTIVA):
    """Paquete ya pagado, como lo deja Webpay al aprobar."""
    p = paquetes.POR_CODIGO[plan]
    return PaqueteClases.objects.create(
        alumno=alumno, profesor=profesor, plan=plan, clases=p.clases, tarifa=profesor.tarifa,
        monto=paquetes.precio(p, profesor.tarifa), dias=p.vigencia_dias, buy_order='LB1234567',
        estado=estado, fecha_fin=timezone.now() + timedelta(days=dias),
    )


class CalculoTests(SimpleTestCase):

    def precios(self, tarifa):
        return [c.precio for c in paquetes.cotizar(tarifa)]

    def test_tarifa_base_da_los_precios_de_referencia(self):
        self.assertEqual(self.precios(15000), [15000, 59000, 116000])

    def test_otra_tarifa_escala_con_el_mismo_descuento(self):
        self.assertEqual(self.precios(20000), [20000, 79000, 155000])
        self.assertEqual(self.precios(10000), [10000, 39000, 77000])

    def test_descuento_por_clase_con_tarifa_base(self):
        flexible, progreso, intensivo = paquetes.cotizar(15000)
        self.assertEqual([flexible.descuento_por_clase, progreso.descuento_por_clase,
                          intensivo.descuento_por_clase], [0, 250, 500])
        self.assertEqual([progreso.precio_por_clase, intensivo.precio_por_clase], [14750, 14500])
        self.assertEqual([progreso.descuento_pct, intensivo.descuento_pct], ['1,7', '3,3'])
        self.assertEqual([progreso.ahorro_total, intensivo.ahorro_total], [1000, 4000])

    def test_cantidad_de_clases_y_vigencia(self):
        self.assertEqual([(p.nombre, p.clases, p.vigencia_dias) for p in paquetes.PLANES],
                         [('Flexible', 1, 30), ('Progreso', 4, 60), ('Intensivo', 8, 90)])

    def test_comision_15_por_ciento_con_iva_incluido(self):
        flexible, progreso, intensivo = paquetes.cotizar(15000)
        self.assertEqual((flexible.comision, flexible.pago_profesor), (2250, 12750))
        self.assertEqual((progreso.comision, progreso.pago_profesor), (8850, 50150))
        self.assertEqual((intensivo.comision, intensivo.pago_profesor), (17400, 98600))
        self.assertEqual(flexible.iva_comision, 359)  # 2.250 x 19/119
        for c in paquetes.cotizar(15000):
            self.assertEqual(c.comision + c.pago_profesor, c.precio)

    def test_validar_tarifa(self):
        self.assertEqual(paquetes.validar_tarifa(' 20000 '), 20000)
        for malo in ('', 'abc', '9000', '50001', '15500', '-15000', None):
            with self.subTest(tarifa=malo), self.assertRaises(ValidationError):
                paquetes.validar_tarifa(malo)


class Escenario(TestCase):
    """Dos alumnos, un profesor habilitado con clase y otro (habilitado) mas, y uno sin titulo."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.ana = crear_alumno(RUT_ANA, 'Ana', genero)
        cls.beto = crear_alumno(RUT_BETO, 'Beto', genero)
        mate = Especialidad.objects.create(nombre='Matematicas')
        cls.profe = crear_profesor(RUT_PROFE, 'profe@lbwus.cl', mate)
        cls.otro = crear_profesor(RUT_OTRO, 'otro@lbwus.cl', mate)
        cls.sin_titulo = crear_profesor(RUT_SIN_TITULO, 'sin@lbwus.cl', mate,
                                        titulo_estado=Profesor.TITULO_EN_REVISION)
        asignatura = Asignatura.objects.create(nombre='Algebra')
        cls.clase = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                         horario=time(10, 0), profesor=cls.profe)
        cls.clase_otro = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                              horario=time(11, 0), profesor=cls.otro)

    def entrar(self, rut):
        self.client.logout()
        self.client.post(reverse('login'), {'username': rut, 'password': CLAVE})


class PaginaPlanesTests(Escenario):

    def test_muestra_los_tres_paquetes_con_precios_de_referencia(self):
        r = self.client.get(reverse('planes'))
        for texto in ('Flexible', 'Progreso', 'Intensivo', '$15.000', '$59.000', '$116.000',
                      '1 clase de 60 min', '4 clases de 60 min', '8 clases de 60 min',
                      '$14.750 por clase', '$14.500 por clase',
                      'Descuento de $250 por clase (1,7%)', 'Descuento de $500 por clase (3,3%)',
                      'comisión LBWUS de 15%', 'IVA incluido', 'Vigencia de 90 días'):
            self.assertContains(r, texto)

    def test_ya_no_ofrece_los_planes_antiguos_ni_funciones_simuladas(self):
        r = self.client.get(reverse('planes'))
        for texto in ('Plan Básico', '$89.990', 'Plan Personalizado', 'Material Específico', 'carrito'):
            self.assertNotContains(r, texto)

    def test_precios_del_profesor_elegido(self):
        self.profe.tarifa = 20000
        self.profe.save()
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        for texto in ('$20.000', '$79.000', '$155.000', 'Precios con Profe'):
            self.assertContains(r, texto)
        self.assertNotContains(r, '$116.000')

    def test_profesor_sin_titulo_o_inexistente_usa_la_referencia(self):
        for pk in (self.sin_titulo.id_profesor, 9999, 'x'):
            r = self.client.get(reverse('planes'), {'profesor': pk})
            self.assertContains(r, '$116.000')
            self.assertIsNone(r.context['profesor'])

    def test_anonimo_no_ve_boton_de_compra(self):
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(r, 'Inicia sesión como alumno para comprar')
        self.assertNotContains(r, reverse('comprar_paquete'))

    def test_alumno_ve_un_formulario_de_compra_por_paquete(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(r, f'action="{reverse("comprar_paquete")}"', count=3)
        for plan in ('flexible', 'progreso', 'intensivo'):
            self.assertContains(r, f'name="plan" value="{plan}"')

    def test_navegacion_a_planes_desde_el_menu(self):
        self.assertContains(self.client.get(reverse('home')), f'href="{reverse("planes")}"')


@patch('alumnos.views._tx')
class CompraTests(Escenario):

    def comprar(self, mock_tx, plan='progreso', profesor=None, **extra):
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse('comprar_paquete'), {
            'plan': plan, 'profesor': (profesor or self.profe).id_profesor, **extra})

    def test_cobra_el_precio_del_servidor_para_cada_paquete(self, mock_tx):
        self.entrar(RUT_ANA)
        for plan, monto, clases in (('flexible', 15000, 1), ('progreso', 59000, 4), ('intensivo', 116000, 8)):
            with self.subTest(plan=plan):
                r = self.comprar(mock_tx, plan)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(mock_tx.return_value.create.call_args[0][2], monto)
                paquete = PaqueteClases.objects.filter(plan=plan).get()
                self.assertEqual((paquete.monto, paquete.clases, paquete.tarifa, paquete.estado),
                                 (monto, clases, 15000, PaqueteClases.ESTADO_PENDIENTE))

    def test_el_precio_enviado_por_el_cliente_se_ignora(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'intensivo', monto='1', amount='1', precio='1', clases='99')
        self.assertEqual(mock_tx.return_value.create.call_args[0][2], 116000)
        self.assertEqual(PaqueteClases.objects.get().clases, 8)

    def test_usa_la_tarifa_del_profesor(self, mock_tx):
        self.profe.tarifa = 20000
        self.profe.save()
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'progreso')
        self.assertEqual(mock_tx.return_value.create.call_args[0][2], 79000)

    def test_sin_sesion_de_alumno_no_cobra(self, mock_tx):
        r = self.comprar(mock_tx)
        self.assertEqual(r.status_code, 302)
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())

    def test_un_profesor_no_puede_comprar(self, mock_tx):
        self.entrar(RUT_PROFE)
        self.comprar(mock_tx)
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())

    def test_get_no_compra(self, mock_tx):
        self.entrar(RUT_ANA)
        self.assertEqual(self.client.get(reverse('comprar_paquete')).status_code, 405)

    def test_datos_invalidos_redirigen_a_planes_sin_cobrar(self, mock_tx):
        self.entrar(RUT_ANA)
        casos = [{'plan': 'gratis', 'profesor': self.profe.id_profesor},
                 {'plan': 'progreso', 'profesor': self.sin_titulo.id_profesor},
                 {'plan': 'progreso', 'profesor': 'x'}, {'plan': 'progreso'}, {}]
        for datos in casos:
            with self.subTest(datos=datos):
                r = self.client.post(reverse('comprar_paquete'), datos)
                self.assertRedirects(r, reverse('planes'))
        mock_tx.return_value.create.assert_not_called()
        self.assertFalse(PaqueteClases.objects.exists())

    def test_cada_compra_tiene_una_orden_unica_y_aprobar_una_no_activa_otra(self, mock_tx):
        self.entrar(RUT_ANA)
        for _ in range(3):
            self.comprar(mock_tx)
        ordenes = list(PaqueteClases.objects.values_list('buy_order', flat=True))
        self.assertEqual(len(set(ordenes)), 3)
        self.assertTrue(all(len(o) <= 26 for o in ordenes))  # limite de Transbank
        mock_tx.return_value.commit.return_value = {'response_code': 0, 'status': 'AUTHORIZED',
                                                    'amount': 59000, 'buy_order': ordenes[0]}
        self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertEqual(PaqueteClases.objects.filter(estado=PaqueteClases.ESTADO_ACTIVA).count(), 1)

    def test_si_transbank_falla_al_crear_no_se_crea_el_paquete(self, mock_tx):
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.side_effect = Exception('Transbank caido')
        r = self.client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        self.assertContains(r, 'Pago Rechazado')
        self.assertFalse(PaqueteClases.objects.exists())

    def test_si_transbank_falla_al_confirmar_no_se_activa(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx)
        mock_tx.return_value.commit.side_effect = Exception('token expirado')
        r = self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertContains(r, 'Pago Rechazado')
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_PENDIENTE)

    def test_monto_autorizado_distinto_al_del_paquete_se_rechaza(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'progreso')  # $59.000
        mock_tx.return_value.commit.return_value = {
            'response_code': 0, 'status': 'AUTHORIZED', 'amount': 1000,
            'buy_order': PaqueteClases.objects.get().buy_order}
        r = self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertContains(r, 'Pago Rechazado')
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_RECHAZADA)

    def confirmar(self, mock_tx, aprobado):
        mock_tx.return_value.commit.return_value = {
            'response_code': 0 if aprobado else -1, 'status': 'AUTHORIZED' if aprobado else 'FAILED',
            'amount': 59000, 'buy_order': PaqueteClases.objects.get().buy_order,
        }
        return self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})

    def test_pago_aprobado_activa_el_paquete_con_su_vigencia(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'progreso')
        r = self.confirmar(mock_tx, aprobado=True)
        self.assertContains(r, 'Progreso: 4 clase(s) con Profe')
        paquete = PaqueteClases.objects.get()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)
        self.assertAlmostEqual((paquete.fecha_fin - timezone.now()).days, 59, delta=1)
        self.assertEqual(paquete.clases_disponibles, 4)

    def test_pago_rechazado_no_da_clases_y_repetir_el_token_no_duplica(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx)
        self.confirmar(mock_tx, aprobado=False)
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_RECHAZADA)
        self.assertEqual(self.ana.paquetes.vigentes().count(), 0)
        self.comprar(mock_tx)
        nuevo = PaqueteClases.objects.exclude(estado=PaqueteClases.ESTADO_RECHAZADA).get()
        for _ in range(2):  # replay del mismo commit
            mock_tx.return_value.commit.return_value = {'response_code': 0, 'status': 'AUTHORIZED',
                                                        'amount': 59000, 'buy_order': nuevo.buy_order}
            self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertEqual(self.ana.paquetes.vigentes().count(), 1)


class ReservaTests(Escenario):

    def reservar(self, alumno, sesion):
        return InscripcionService.inscribir_alumno_en_sesion(alumno, sesion.pk)

    def sesiones(self, n, clase=None, desde=1):
        return [crear_sesion(clase or self.clase, dias=desde + i) for i in range(n)]

    def test_sin_paquete_no_se_puede_reservar(self):
        sesion, = self.sesiones(1)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, sesion)
        self.assertFalse(Inscripcion.objects.exists())

    def test_cada_paquete_permite_exactamente_sus_clases(self):
        for plan, clases in (('flexible', 1), ('progreso', 4), ('intensivo', 8)):
            with self.subTest(plan=plan):
                alumno = crear_alumno(f'7000000{clases}-0', plan, Genero.objects.first())
                paquete = dar_paquete(alumno, self.profe, plan)
                sesiones = self.sesiones(clases + 1)
                for sesion in sesiones[:clases]:
                    self.reservar(alumno, sesion)
                self.assertEqual((paquete.clases_usadas, paquete.clases_disponibles), (clases, 0))
                with self.assertRaises(SinClasesDisponiblesError):
                    self.reservar(alumno, sesiones[clases])
                Inscripcion.objects.all().delete()
                SesionClase.objects.all().delete()

    def test_la_reserva_queda_ligada_al_paquete_y_confirmada(self):
        paquete = dar_paquete(self.ana, self.profe)
        insc = self.reservar(self.ana, self.sesiones(1)[0])
        self.assertEqual((insc.paquete, insc.estado), (paquete, Inscripcion.ESTADO_CONFIRMADA))

    def test_paquete_de_otro_profesor_pendiente_o_ajeno_no_sirve(self):
        sesion, = self.sesiones(1)
        dar_paquete(self.ana, self.otro)
        dar_paquete(self.ana, self.profe, estado=PaqueteClases.ESTADO_PENDIENTE)
        dar_paquete(self.beto, self.profe)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, sesion)

    def test_paquete_vencido_o_sesion_fuera_de_la_vigencia(self):
        dar_paquete(self.ana, self.profe, 'flexible', dias=5)
        lejana, = self.sesiones(1, desde=10)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, lejana)
        PaqueteClases.objects.update(fecha_fin=timezone.now() - timedelta(days=1))
        cercana, = self.sesiones(1, desde=2)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, cercana)

    def test_se_gasta_el_paquete_que_vence_primero(self):
        largo = dar_paquete(self.ana, self.profe, 'intensivo', dias=80)
        corto = dar_paquete(self.ana, self.profe, 'flexible', dias=10)
        self.assertEqual(self.reservar(self.ana, self.sesiones(1)[0]).paquete, corto)
        self.assertEqual(self.reservar(self.ana, self.sesiones(1, desde=3)[0]).paquete, largo)

    def test_cancelar_devuelve_la_clase_y_se_puede_volver_a_reservar(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        sesion, = self.sesiones(1)
        insc = self.reservar(self.ana, sesion)
        self.assertEqual(paquete.clases_disponibles, 0)
        InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(paquete.clases_disponibles, 1)
        self.assertEqual(self.reservar(self.ana, sesion).paquete, paquete)

    def test_cancelar_dos_veces_no_devuelve_dos_clases(self):
        paquete = dar_paquete(self.ana, self.profe)
        insc = self.reservar(self.ana, self.sesiones(1)[0])
        InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        with self.assertRaises(InscripcionError):
            InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(paquete.clases_disponibles, 4)

    def test_no_se_cancela_una_clase_que_ya_empezo(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        pasada = crear_sesion(self.clase, dias=-1)
        insc = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=pasada, paquete=paquete)
        with self.assertRaises(InscripcionError):
            InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(paquete.clases_disponibles, 0)

    def test_si_el_profesor_cancela_la_sesion_la_clase_vuelve(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        sesion, = self.sesiones(1)
        self.reservar(self.ana, sesion)
        sesion.estado = SesionClase.ESTADO_CANCELADA
        sesion.save()
        self.assertEqual(paquete.clases_disponibles, 1)

    def test_la_vista_de_cancelar_no_borra_una_clase_empezada(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        pasada = crear_sesion(self.clase, dias=-1)
        insc = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=pasada, paquete=paquete)
        self.entrar(RUT_ANA)
        self.client.post(reverse('cancelar_inscripcion', args=[insc.pk]))
        insc.refresh_from_db()
        self.assertEqual(insc.estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_otro_alumno_no_puede_cancelar_mi_reserva(self):
        dar_paquete(self.ana, self.profe)
        insc = self.reservar(self.ana, self.sesiones(1)[0])
        self.entrar(RUT_BETO)
        self.client.post(reverse('cancelar_inscripcion', args=[insc.pk]))
        insc.refresh_from_db()
        self.assertEqual(insc.estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_endpoint_de_reserva_responde_sin_clases(self):
        sesion, = self.sesiones(1)
        self.entrar(RUT_ANA)
        r = self.client.post(reverse('reservar_sesion'), {'id_sesion': sesion.pk}).json()
        self.assertFalse(r['success'])
        self.assertIn('Compra un paquete', r['message'])

    def test_endpoint_de_reserva_con_paquete(self):
        dar_paquete(self.ana, self.profe)
        sesion, = self.sesiones(1)
        self.entrar(RUT_ANA)
        self.assertTrue(self.client.post(reverse('reservar_sesion'), {'id_sesion': sesion.pk}).json()['success'])


class ReprogramacionTests(Escenario):

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)
        self.s1, self.s2, self.s3 = (crear_sesion(self.clase, dias=d) for d in (1, 2, 3))
        self.insc = InscripcionService.inscribir_alumno_en_sesion(self.ana, self.s1.pk)

    def mover(self, sesion, alumno=None):
        return InscripcionService.reprogramar_inscripcion(alumno or self.ana, self.insc.pk, sesion.pk)

    def test_mueve_la_reserva_sin_gastar_otra_clase(self):
        movida = self.mover(self.s2)
        self.assertEqual((movida.sesion, movida.paquete), (self.s2, self.paquete))
        self.assertEqual((self.paquete.clases_usadas, self.paquete.clases_disponibles), (1, 3))
        self.assertEqual(self.s1.inscripciones.filter(estado='confirmada').count(), 0)

    def test_no_se_puede_con_otro_profesor(self):
        ajena = crear_sesion(self.clase_otro, dias=2)
        with self.assertRaisesMessage(InscripcionError, 'mismo profesor'):
            self.mover(ajena)

    def test_misma_sesion_sesion_cancelada_o_pasada(self):
        cancelada = crear_sesion(self.clase, dias=4, estado=SesionClase.ESTADO_CANCELADA)
        pasada = crear_sesion(self.clase, dias=-1)
        with self.assertRaises(InscripcionError):
            self.mover(self.s1)
        for sesion in (cancelada, pasada):
            with self.assertRaises(SesionNoDisponibleError):
                self.mover(sesion)

    def test_sin_cupo(self):
        llena = crear_sesion(self.clase, dias=5, cupo=1)
        dar_paquete(self.beto, self.profe)
        InscripcionService.inscribir_alumno_en_sesion(self.beto, llena.pk)
        with self.assertRaises(CupoAgotadoError):
            self.mover(llena)

    def test_profesor_sin_titulo_vigente(self):
        Profesor.objects.filter(pk=self.profe.pk).update(titulo_estado=Profesor.TITULO_EN_REVISION)
        with self.assertRaises(SesionNoDisponibleError):
            self.mover(self.s2)

    def test_ya_reservada_por_el_alumno(self):
        InscripcionService.inscribir_alumno_en_sesion(self.ana, self.s2.pk)
        with self.assertRaises(InscripcionDuplicadaError):
            self.mover(self.s2)

    def test_fuera_de_la_vigencia_del_paquete(self):
        lejana = crear_sesion(self.clase, dias=90)
        with self.assertRaises(SinClasesDisponiblesError):
            self.mover(lejana)

    def test_no_se_reprograma_una_clase_que_ya_empezo(self):
        pasada = crear_sesion(self.clase, dias=-2)
        vieja = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=pasada, paquete=self.paquete)
        with self.assertRaises(InscripcionError):
            InscripcionService.reprogramar_inscripcion(self.ana, vieja.pk, self.s3.pk)

    def test_una_reserva_cancelada_no_se_reprograma(self):
        InscripcionService.cancelar_inscripcion(self.ana, self.insc.pk)
        with self.assertRaises(InscripcionError):
            self.mover(self.s2)

    def test_otro_alumno_no_puede_reprogramar_mi_reserva(self):
        with self.assertRaises(InscripcionError):
            self.mover(self.s2, alumno=self.beto)

    def test_endpoint_permisos_y_resultado(self):
        url = reverse('reprogramar_inscripcion', args=[self.insc.pk])
        self.assertEqual(self.client.post(url, {'id_sesion': self.s2.pk}).status_code, 302)  # sin sesion
        self.entrar(RUT_BETO)
        self.assertFalse(self.client.post(url, {'id_sesion': self.s2.pk}).json()['success'])
        self.entrar(RUT_ANA)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'id_sesion': 'x'}).status_code, 400)
        self.assertTrue(self.client.post(url, {'id_sesion': self.s2.pk}).json()['success'])
        self.insc.refresh_from_db()
        self.assertEqual(self.insc.sesion, self.s2)


class PortalYSaldoTests(Escenario):

    def test_el_portal_muestra_las_clases_que_quedan(self):
        paquete = dar_paquete(self.ana, self.profe, 'progreso')
        InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=1).pk)
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertEqual(r.context['plan_activo'], {'nombre': 'Progreso', 'premium': True})
        self.assertContains(r, 'de 4 clases disponibles')
        self.assertContains(r, f'<span class="pp-price">{paquete.clases_disponibles}</span>')
        self.assertNotContains(r, 'agregarPlanPortal')

    def test_reprogramar_y_cancelar_solo_en_reservas_que_no_empezaron(self):
        paquete = dar_paquete(self.ana, self.profe, 'progreso')
        futura = InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=1).pk)
        pasada = Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                            sesion=crear_sesion(self.clase, dias=-1))
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, 'aria-label="Reprogramar clase"', count=1)
        self.assertContains(r, f', {futura.id_inscripcion})">')  # el boton es de la reserva futura
        self.assertNotContains(r, f', {pasada.id_inscripcion})">')
        self.assertContains(r, reverse('cancelar_inscripcion', args=[futura.pk]))
        self.assertNotContains(r, reverse('cancelar_inscripcion', args=[pasada.pk]))
        self.assertNotContains(r, 'Valor: ${s.precio_formateado}')  # el precio es el paquete, no la sesion

    def test_sin_paquetes_el_portal_lo_dice(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertIsNone(r.context['plan_activo'])
        self.assertContains(r, 'Aún no tienes paquetes vigentes')

    def test_el_profesor_recibe_el_85_por_ciento_de_cada_clase_tomada(self):
        dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (1, 2):
            InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=dias).pk)
        saldos = calcular_saldos(self.profe)
        self.assertEqual(saldos['total_ganado'], 2 * 14500)
        self.assertEqual(saldos['disponible'], 2 * paquetes.pago_profesor(14500))
        self.assertEqual(saldos['pendiente'], 2 * (14500 - paquetes.pago_profesor(14500)))

    def test_clase_cancelada_no_le_paga_al_profesor(self):
        dar_paquete(self.ana, self.profe, 'flexible')
        insc = InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=1).pk)
        InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(calcular_saldos(self.profe)['total_ganado'], 0)

    def test_el_profesor_cambia_su_tarifa_desde_el_panel_con_validacion(self):
        self.entrar(RUT_PROFE)
        base = {'nombre': 'Profe', 'rut': RUT_PROFE, 'especialidad': self.profe.especialidad_id,
                'direccion': 'Calle 1', 'correo_electronico': 'profe@lbwus.cl',
                'telefono': '911111111', 'genero': self.profe.user.genero.id_genero}
        url = reverse('actualizar_perfil_prof')
        self.assertTrue(self.client.post(url, {**base, 'tarifa': '20000'}).json()['success'])
        self.profe.refresh_from_db()
        self.assertEqual(self.profe.tarifa, 20000)
        for malo in ('100', '99999', 'abc', '15500'):
            r = self.client.post(url, {**base, 'tarifa': malo}).json()
            self.assertFalse(r['success'], malo)
        self.assertTrue(self.client.post(url, base).json()['success'])  # sin tarifa: no cambia
        self.profe.refresh_from_db()
        self.assertEqual(self.profe.tarifa, 20000)

    def test_lo_ya_vendido_no_cambia_si_el_profesor_sube_su_tarifa(self):
        paquete = dar_paquete(self.ana, self.profe, 'progreso')
        self.profe.tarifa = 30000
        self.profe.save()
        paquete.refresh_from_db()
        self.assertEqual((paquete.monto, paquete.tarifa), (59000, 15000))
