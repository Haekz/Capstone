"""Paquetes de clases Flexible / Progreso / Intensivo (analisis de mercado 2.13-2.14, F-11).

Precios fijos de LBWUS, iguales con todos los profesores: $18.990 / $74.990 / $146.990, con una
comision de LBWUS del 26% (IVA incluido; decididos 25-nov-2026). Cubre precio, cantidad de clases,
compra, reserva, cancelacion, reprogramacion y permisos. Webpay va con mock.
"""

import re
from datetime import timedelta
from unittest.mock import patch

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
from tests.aceptacion import aceptar_terminos
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
        alumno=alumno, profesor=profesor, plan=plan, clases=p.clases, tarifa=paquetes.TARIFA,
        monto=paquetes.precio(p), dias=p.vigencia_dias, buy_order='LB1234567',
        estado=estado, fecha_fin=timezone.now() + timedelta(days=dias),
    )


class CalculoTests(SimpleTestCase):

    def precios(self):
        return [c.precio for c in paquetes.cotizar()]

    def test_precios_fijos_de_lbwus(self):
        self.assertEqual(paquetes.TARIFA, 18990)
        self.assertEqual(self.precios(), [18990, 74990, 146990])

    def test_todo_precio_termina_en_990(self):
        for precio in self.precios():
            self.assertEqual(precio % 1000, 990, precio)

    def test_descuento_por_clase(self):
        flexible, progreso, intensivo = paquetes.cotizar()
        self.assertEqual([flexible.descuento_por_clase, progreso.descuento_por_clase,
                          intensivo.descuento_por_clase], [0, 242, 616])
        # Al peso mas cercano (25-nov): $74.990 / 4 = $18.747,5 y $146.990 / 8 = $18.373,75
        self.assertEqual([progreso.precio_por_clase, intensivo.precio_por_clase], [18748, 18374])
        # Sobre el ahorro total, como la tabla de precios: 970 / 75.960 y 4.930 / 151.920
        self.assertEqual([progreso.descuento_pct, intensivo.descuento_pct], ['1,28', '3,25'])
        self.assertEqual([progreso.ahorro_total, intensivo.ahorro_total], [970, 4930])

    def test_cantidad_de_clases_y_vigencia(self):
        self.assertEqual([(p.nombre, p.clases, p.vigencia_dias) for p in paquetes.PLANES],
                         [('Flexible', 1, 30), ('Progreso', 4, 30), ('Intensivo', 8, 60)])  # decidido 14-nov

    def test_comision_26_por_ciento_con_iva_incluido(self):
        flexible, progreso, intensivo = paquetes.cotizar()
        self.assertEqual((flexible.comision, flexible.pago_profesor), (4937, 14053))
        self.assertEqual((progreso.comision, progreso.pago_profesor), (19497, 55493))
        self.assertEqual((intensivo.comision, intensivo.pago_profesor), (38217, 108773))
        self.assertEqual(flexible.iva_comision, 788)  # 4.937 x 19/119
        for c in paquetes.cotizar():
            self.assertEqual(c.comision + c.pago_profesor, c.precio)


class Escenario(TestCase):
    """Dos alumnos, un profesor habilitado con clase y otro (habilitado) mas, y uno sin titulo."""

    @classmethod
    def setUpTestData(cls):
        genero = Genero.objects.create(descripcion='Otro')
        cls.ana = crear_alumno(RUT_ANA, 'Ana', genero)
        cls.beto = crear_alumno(RUT_BETO, 'Beto', genero)
        for alumno in (cls.ana, cls.beto):
            aceptar_terminos(alumno.user)  # estas pruebas son de compra, no de la aceptacion
        mate = Especialidad.objects.create(nombre='Matematicas')
        cls.profe = crear_profesor(RUT_PROFE, 'profe@lbwus.cl', mate)
        cls.otro = crear_profesor(RUT_OTRO, 'otro@lbwus.cl', mate)
        cls.sin_titulo = crear_profesor(RUT_SIN_TITULO, 'sin@lbwus.cl', mate,
                                        titulo_estado=Profesor.TITULO_EN_REVISION)
        asignatura = Asignatura.objects.create(nombre='Algebra')
        cls.clase = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                         profesor=cls.profe)
        cls.clase_otro = Clase.objects.create(asignatura=asignatura, modalidad='online',
                                              profesor=cls.otro)

    def entrar(self, rut):
        self.client.logout()
        self.client.post(reverse('login'), {'username': rut, 'password': CLAVE})


class PaginaPlanesTests(Escenario):

    def test_muestra_los_tres_paquetes_con_precios_de_referencia(self):
        r = self.client.get(reverse('planes'))
        for texto in ('Flexible', 'Progreso', 'Intensivo', '$18.990', '$74.990', '$146.990',
                      '1 clase de 60 min', '4 clases de 60 min', '8 clases de 60 min',
                      '$18.748 por clase', '$18.374 por clase',
                      'Descuento de $242 por clase (1,28%)', 'Descuento de $616 por clase (3,25%)',
                      'comisión LBWUS de 26%', 'IVA incluido', 'Vigencia de 30 días', 'Vigencia de 60 días'):
            self.assertContains(r, texto)

    def test_condiciones_dicen_las_vigencias_de_planes(self):
        """20-nov: decia 30/60/90 escrito a mano cuando ya eran 30/30/60. Las tarjetas estaban bien, por eso la prueba
        de arriba no lo veia: aqui se mira solo la seccion Condiciones."""
        html = self.client.get(reverse('planes')).content.decode()
        condiciones = html.split('id="pl-condiciones-titulo"', 1)[1].split('</section>', 1)[0]
        self.assertEqual(re.findall(r'(\d+) días \((\w+)\)', condiciones),
                         [(str(plan.vigencia_dias), plan.nombre) for plan in paquetes.PLANES])

    def test_ya_no_ofrece_los_planes_antiguos_ni_funciones_simuladas(self):
        r = self.client.get(reverse('planes'))
        for texto in ('Plan Básico', '$89.990', 'Plan Personalizado', 'Material Específico', 'carrito'):
            self.assertNotContains(r, texto)

    def test_mismos_precios_con_cualquier_profesor(self):
        for profesor in (self.profe, self.otro):
            r = self.client.get(reverse('planes'), {'profesor': profesor.id_profesor})
            for texto in ('$18.990', '$74.990', '$146.990', f'Precios con {profesor.nombre}',
                          'el mismo precio con todos los profesores'):
                self.assertContains(r, texto)

    def test_profesor_sin_titulo_o_inexistente_usa_la_referencia(self):
        for pk in (self.sin_titulo.id_profesor, 9999, 'x'):
            r = self.client.get(reverse('planes'), {'profesor': pk})
            self.assertContains(r, '$146.990')
            self.assertIsNone(r.context['profesor'])

    def test_anonimo_no_ve_boton_de_compra(self):
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(r, 'Inicia sesión como alumno para comprar')
        self.assertNotContains(r, reverse('comprar_paquete'))

    def test_sin_profesor_elegido_no_hay_selector_ni_boton_que_no_haga_nada(self):
        r = self.client.get(reverse('planes'))
        self.assertNotContains(r, 'id="pl-profesor"')
        self.assertNotContains(r, 'Elige un profesor para comprar')

    def test_anonimo_sin_profesor_va_al_login_y_de_ahi_al_buscador(self):
        r = self.client.get(reverse('planes'))
        self.assertContains(r, f'{reverse("login")}?next={reverse("alumno_pag1")}', count=3)

    def test_alumno_sin_profesor_va_al_buscador_de_su_portal(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('planes'))
        self.assertContains(r, f'{reverse("alumno_pag1")}#dashboard-search-input', count=3)
        self.assertContains(r, 'Buscar un profesor', count=3)

    def test_alumno_ve_un_formulario_de_compra_por_paquete(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('planes'), {'profesor': self.profe.id_profesor})
        self.assertContains(r, f'action="{reverse("comprar_paquete")}"', count=3)
        for plan in ('flexible', 'progreso', 'intensivo'):
            self.assertContains(r, f'name="plan" value="{plan}"')

    def test_navegacion_a_planes_desde_el_menu(self):
        self.assertContains(self.client.get(reverse('home')), f'href="{reverse("planes")}"')


@patch('alumnos.webpay._tx')
class CompraTests(Escenario):

    def comprar(self, mock_tx, plan='progreso', profesor=None, **extra):
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        return self.client.post(reverse('comprar_paquete'), {
            'plan': plan, 'profesor': (profesor or self.profe).id_profesor, **extra})

    def test_cobra_el_precio_del_servidor_para_cada_paquete(self, mock_tx):
        self.entrar(RUT_ANA)
        for plan, monto, clases in (('flexible', 18990, 1), ('progreso', 74990, 4), ('intensivo', 146990, 8)):
            with self.subTest(plan=plan):
                r = self.comprar(mock_tx, plan)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(mock_tx.return_value.create.call_args[0][2], monto)
                paquete = PaqueteClases.objects.filter(plan=plan).get()
                self.assertEqual((paquete.monto, paquete.clases, paquete.tarifa, paquete.estado),
                                 (monto, clases, 18990, PaqueteClases.ESTADO_PENDIENTE))

    def test_el_precio_enviado_por_el_cliente_se_ignora(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'intensivo', monto='1', amount='1', precio='1', clases='99')
        self.assertEqual(mock_tx.return_value.create.call_args[0][2], 146990)
        self.assertEqual(PaqueteClases.objects.get().clases, 8)

    def test_cobra_lo_mismo_con_cualquier_profesor(self, mock_tx):
        self.entrar(RUT_ANA)
        for profesor in (self.profe, self.otro):
            with self.subTest(profesor=profesor.nombre):
                self.comprar(mock_tx, 'progreso', profesor=profesor)
                self.assertEqual(mock_tx.return_value.create.call_args[0][2], 74990)

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
                                                    'amount': 74990, 'buy_order': ordenes[0]}
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
        self.comprar(mock_tx, 'progreso')  # $62.990
        mock_tx.return_value.commit.return_value = {
            'response_code': 0, 'status': 'AUTHORIZED', 'amount': 1000,
            'buy_order': PaqueteClases.objects.get().buy_order}
        r = self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertContains(r, 'Pago Rechazado')
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_RECHAZADA)

    def confirmar(self, mock_tx, aprobado):
        mock_tx.return_value.commit.return_value = {
            'response_code': 0 if aprobado else -1, 'status': 'AUTHORIZED' if aprobado else 'FAILED',
            'amount': 74990, 'buy_order': PaqueteClases.objects.get().buy_order,
        }
        return self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})

    def test_pago_aprobado_activa_el_paquete_con_su_vigencia(self, mock_tx):
        self.entrar(RUT_ANA)
        self.comprar(mock_tx, 'progreso')
        r = self.confirmar(mock_tx, aprobado=True)
        self.assertContains(r, 'Progreso: 4 clase(s) con Profe')
        paquete = PaqueteClases.objects.get()
        self.assertEqual(paquete.estado, PaqueteClases.ESTADO_ACTIVA)
        vigencia = paquetes.POR_CODIGO['progreso'].vigencia_dias
        self.assertEqual(paquete.dias, vigencia)
        self.assertAlmostEqual((paquete.fecha_fin - timezone.now()).days, vigencia - 1, delta=1)
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
                                                        'amount': 74990, 'buy_order': nuevo.buy_order}
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
        self.assertEqual(self.client.post(url, {'id_sesion': self.s2.pk}).status_code, 401)  # sin sesion
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

    def test_el_profesor_recibe_el_74_por_ciento_de_cada_clase_tomada(self):
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (-1, -2):
            Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                       sesion=crear_sesion(self.clase, dias=dias))
        saldos = calcular_saldos(self.profe)
        self.assertEqual(saldos['total_ganado'], 2 * 18374)  # $146.990 / 8, al peso mas cercano
        self.assertEqual(saldos['disponible'], 2 * paquetes.pago_profesor(18374))
        self.assertEqual(saldos['pendiente'], 2 * (18374 - paquetes.pago_profesor(18374)))

    def test_reserva_futura_no_suma_saldo_hasta_dictarse(self):
        dar_paquete(self.ana, self.profe, 'intensivo')
        InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=1).pk)
        saldos = calcular_saldos(self.profe)
        self.assertEqual(saldos['total_ganado'], 0)
        self.assertEqual(saldos['disponible'], 0)

    def test_clase_cancelada_no_le_paga_al_profesor(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                   sesion=crear_sesion(self.clase, dias=-1),
                                   estado=Inscripcion.ESTADO_CANCELADA)
        self.assertEqual(calcular_saldos(self.profe)['total_ganado'], 0)

    def test_el_profesor_ya_no_elige_el_precio(self):
        self.entrar(RUT_PROFE)
        self.assertNotContains(self.client.get(reverse('panel_profesor')), 'name="tarifa"')
        base = {'nombre': 'Profe', 'rut': RUT_PROFE, 'especialidad': self.profe.especialidad_id,
                'direccion': 'Calle 1', 'correo_electronico': 'profe@lbwus.cl',
                'telefono': '911111111', 'genero': self.profe.user.genero.id_genero}
        # Un formulario viejo que aun mande 'tarifa' guarda el resto y el precio no cambia.
        r = self.client.post(reverse('actualizar_perfil_prof'), {**base, 'tarifa': '50000'})
        self.assertTrue(r.json()['success'])
        self.assertEqual([c.precio for c in paquetes.cotizar()], [18990, 74990, 146990])

    def test_lo_ya_vendido_no_cambia_con_los_precios_nuevos(self):
        """Un paquete pagado con los precios antiguos conserva su monto y su valor por clase."""
        paquete = dar_paquete(self.ana, self.profe, 'progreso')
        PaqueteClases.objects.filter(pk=paquete.pk).update(monto=59000, tarifa=15000)
        paquete.refresh_from_db()
        self.assertEqual((paquete.monto, paquete.tarifa, paquete.precio_por_clase), (59000, 15000, 14750))


class CriteriosSaldosScrum85Tests(Escenario):
    """SCRUM-85 (S4-05): brechas de la matriz de saldos que no cubrian las clases de arriba.

    Saldo = clases del paquete - inscripciones.consumidas(): no se resta ni se suma,
    se cuenta. Por eso cancelar devuelve la clase y reprogramar no gasta otra.
    """

    def reservar(self, alumno, sesion):
        return InscripcionService.inscribir_alumno_en_sesion(alumno, sesion.pk)

    @patch('alumnos.webpay._tx')
    def test_compra_aprobada_de_cada_plan_deja_su_saldo(self, mock_tx):
        self.entrar(RUT_ANA)
        for plan, monto, clases in (('flexible', 18990, 1), ('progreso', 74990, 4), ('intensivo', 146990, 8)):
            with self.subTest(plan=plan):
                token = f'tok-{plan}'  # cada transaccion de Webpay trae su propio token
                mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': token}
                self.client.post(reverse('comprar_paquete'), {'plan': plan, 'profesor': self.profe.id_profesor})
                paquete = PaqueteClases.objects.get(plan=plan)
                mock_tx.return_value.commit.return_value = {
                    'response_code': 0, 'status': 'AUTHORIZED', 'amount': monto, 'buy_order': paquete.buy_order}
                self.client.post(reverse('confirmacion'), {'token_ws': token})
                paquete.refresh_from_db()
                self.assertEqual((paquete.estado, paquete.clases_disponibles), (PaqueteClases.ESTADO_ACTIVA, clases))

    @patch('alumnos.webpay._tx')
    def test_orden_desconocida_no_activa_ningun_paquete(self, mock_tx):
        """Reemplaza a test_03 de test_seguridad_webpay_honorarios (buy_order cruzada, flujo antiguo)."""
        dar_paquete(self.ana, self.profe, estado=PaqueteClases.ESTADO_PENDIENTE)
        mock_tx.return_value.commit.return_value = {
            'response_code': 0, 'status': 'AUTHORIZED', 'amount': 74990, 'buy_order': 'PQ-ORDEN-AJENA'}
        self.client.post(reverse('confirmacion'), {'token_ws': 'tok'})
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_PENDIENTE)
        self.assertEqual(self.ana.paquetes.vigentes().count(), 0)

    @patch('alumnos.webpay._tx')
    def test_compra_anulada_deja_el_paquete_pendiente_y_sin_uso(self, mock_tx):
        """TBK_TOKEN (el alumno anula en Webpay): no se activa ni se llama a commit()."""
        self.entrar(RUT_ANA)
        mock_tx.return_value.create.return_value = {'url': 'https://webpay.test/', 'token': 'tok'}
        self.client.post(reverse('comprar_paquete'), {'plan': 'progreso', 'profesor': self.profe.id_profesor})
        r = self.client.post(reverse('confirmacion'), {'TBK_TOKEN': 'tok'})
        self.assertTrue(r.context['anulado'])
        mock_tx.return_value.commit.assert_not_called()
        self.assertEqual(PaqueteClases.objects.get().estado, PaqueteClases.ESTADO_PENDIENTE)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, crear_sesion(self.clase, dias=1))

    def test_paquete_rechazado_no_se_usa(self):
        dar_paquete(self.ana, self.profe, estado=PaqueteClases.ESTADO_RECHAZADA)
        with self.assertRaises(SinClasesDisponiblesError):
            self.reservar(self.ana, crear_sesion(self.clase, dias=1))

    def test_reservar_descuenta_exactamente_una_clase(self):
        paquete = dar_paquete(self.ana, self.profe)
        self.reservar(self.ana, crear_sesion(self.clase, dias=1))
        self.assertEqual((paquete.clases_usadas, paquete.clases_disponibles), (1, 3))

    def test_misma_sesion_dos_veces_se_rechaza_y_descuenta_una(self):
        paquete = dar_paquete(self.ana, self.profe)
        sesion = crear_sesion(self.clase, dias=1)
        self.reservar(self.ana, sesion)
        with self.assertRaises(InscripcionDuplicadaError):
            self.reservar(self.ana, sesion)
        self.assertEqual(paquete.clases_disponibles, 3)

    def test_cancelar_devuelve_la_clase_y_libera_el_cupo(self):
        paquete = dar_paquete(self.ana, self.profe, 'flexible')
        dar_paquete(self.beto, self.profe, 'flexible')
        sesion = crear_sesion(self.clase, dias=1, cupo=1)
        insc = self.reservar(self.ana, sesion)
        with self.assertRaises(CupoAgotadoError):
            self.reservar(self.beto, sesion)
        InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(paquete.clases_disponibles, 1)
        self.assertEqual(self.reservar(self.beto, sesion).estado, Inscripcion.ESTADO_CONFIRMADA)

    def test_reprogramar_y_cancelar_deja_el_saldo_completo(self):
        paquete = dar_paquete(self.ana, self.profe)
        s1, s2, s3 = (crear_sesion(self.clase, dias=d) for d in (1, 2, 3))
        insc = self.reservar(self.ana, s1)
        InscripcionService.reprogramar_inscripcion(self.ana, insc.pk, s2.pk)
        InscripcionService.reprogramar_inscripcion(self.ana, insc.pk, s3.pk)
        self.assertEqual((paquete.clases_usadas, paquete.clases_disponibles), (1, 3))
        InscripcionService.cancelar_inscripcion(self.ana, insc.pk)
        self.assertEqual(paquete.clases_disponibles, 4)
