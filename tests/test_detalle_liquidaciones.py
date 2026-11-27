"""Detalle de liquidaciones del docente (21-nov): cada clase dictada y cada video compartido que suma a su saldo.

Antes la tarjeta recorria `desgloses_profesor`, que ninguna vista pasaba desde que se borro el carrito antiguo: todo docente
leia «Aun no hay operaciones», tuviera cobros o no. Ahora usa la misma cuenta que el saldo (user_profesor/saldos.py).
"""

from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import Inscripcion, PaqueteClases
from alumnos.models.videos import VideoCompartido
from alumnos.templatetags.dinero import clp
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete
from tests.test_pulido_docente_cuenta import _seccion
from user_profesor import detalle_liquidaciones
from user_profesor.saldos import calcular_saldos


class Armado(Escenario):
    """Solo los ayudantes para armar clases dictadas y videos compartidos; sin pruebas propias."""

    def dictar(self, paquete, dias=-1, estado=Inscripcion.ESTADO_CONFIRMADA, alumno=None):
        return Inscripcion.objects.create(alumno=alumno or self.ana, clase=self.clase, paquete=paquete, estado=estado,
                                          sesion=crear_sesion(self.clase, dias=dias))

    def paquete_con_videos(self, videos=4):
        return PaqueteClases.objects.create(
            alumno=self.ana, profesor=self.profe, plan='progreso', clases=4, tarifa=15000, monto=59000, videos=videos,
            monto_videos=videos * paquetes.PRECIO_VIDEO, dias=60, buy_order=f'PQ{PaqueteClases.objects.count():024d}',
            estado=PaqueteClases.ESTADO_ACTIVA, fecha_fin=timezone.now() + timedelta(days=60))

    def compartir(self, paquete, cuantos=1):
        VideoCompartido.objects.bulk_create(
            [VideoCompartido(paquete=paquete, video_id=f'{paquete.pk:012d}{n:012d}') for n in range(cuantos)])


class DetalleDeLiquidacionesTests(Armado):

    def test_cada_clase_dictada_es_una_fila_con_su_comision_y_su_abono(self):
        self.dictar(dar_paquete(self.ana, self.profe, 'intensivo'))
        operaciones, total = detalle_liquidaciones.detalle(self.profe)
        self.assertEqual(total, 1)
        (operacion,) = operaciones
        self.assertEqual((operacion.concepto, operacion.bruto), ('Clase dictada', 18374))  # $146.990 / 8, al peso mas cercano
        self.assertEqual((operacion.comision, operacion.abono),
                         (paquetes.comision(18374), paquetes.pago_profesor(18374)))
        self.assertEqual(operacion.comision + operacion.abono, operacion.bruto)
        self.assertEqual(operacion.alumno, f'{self.ana.user.first_name} {self.ana.user.last_name}'.strip())

    def test_la_cancelada_con_menos_de_4_horas_tambien_se_paga_y_lo_dice(self):
        self.dictar(dar_paquete(self.ana, self.profe, 'flexible'), estado=Inscripcion.ESTADO_CANCELADA_TARDE)
        (operacion,), _ = detalle_liquidaciones.detalle(self.profe)
        self.assertEqual(operacion.concepto, 'Clase cancelada con menos de 4 h')

    def test_cada_video_compartido_es_una_fila_con_la_comision_de_videos(self):
        self.compartir(self.paquete_con_videos(), 2)
        operaciones, total = detalle_liquidaciones.detalle(self.profe)
        self.assertEqual(total, 2)
        for operacion in operaciones:
            self.assertEqual((operacion.concepto, operacion.bruto), ('Video compartido', paquetes.PRECIO_VIDEO))
            self.assertEqual((operacion.comision, operacion.abono), (1300, 3700))  # 26% y 74%

    def test_no_aparece_lo_que_no_suma_al_saldo(self):
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, paquete=paquete,
                                   sesion=crear_sesion(self.clase, dias=1))  # reserva futura
        self.dictar(paquete, dias=-2, estado=Inscripcion.ESTADO_CANCELADA)  # cancelada a tiempo: vuelve al alumno
        paquete_videos = self.paquete_con_videos(videos=1)
        self.compartir(paquete_videos)
        VideoCompartido.objects.update(retirado=timezone.now())  # soporte lo retiro
        self.assertEqual(detalle_liquidaciones.detalle(self.profe), ([], 0))

    def test_cada_profesor_ve_solo_lo_suyo(self):
        self.dictar(dar_paquete(self.ana, self.profe, 'intensivo'))
        self.assertEqual(detalle_liquidaciones.detalle(self.otro), ([], 0))

    def test_las_filas_suman_exactamente_lo_que_dice_el_saldo(self):
        """El detalle y el saldo son la misma cuenta: la suma del abono es lo disponible; la de comisiones, lo pendiente."""
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (-1, -2, -3):
            self.dictar(paquete, dias=dias)
        self.dictar(dar_paquete(self.beto, self.profe, 'progreso'), dias=-4, estado=Inscripcion.ESTADO_CANCELADA_TARDE,
                    alumno=self.beto)
        self.compartir(self.paquete_con_videos(), 3)
        operaciones, total = detalle_liquidaciones.detalle(self.profe, maximo=1000)
        self.assertEqual(total, 7)
        self.assertEqual(calcular_saldos(self.profe), {
            'total_ganado': sum(o.bruto for o in operaciones),
            'disponible': sum(o.abono for o in operaciones),
            'pendiente': sum(o.comision for o in operaciones),
        })

    def test_de_la_mas_reciente_a_la_mas_antigua_y_con_tope(self):
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (-3, -1, -2):
            self.dictar(paquete, dias=dias)
        operaciones, total = detalle_liquidaciones.detalle(self.profe, maximo=2)
        self.assertEqual((len(operaciones), total), (2, 3))
        self.assertGreater(operaciones[0].fecha, operaciones[1].fecha)
        todas, _ = detalle_liquidaciones.detalle(self.profe)
        self.assertEqual([o.fecha for o in todas], sorted((o.fecha for o in todas), reverse=True))


class DetalleEnElPanelTests(Armado):
    """La tarjeta del panel del docente, con los datos reales."""

    def saldo(self):
        self.entrar(RUT_PROFE)
        return _seccion(self.client.get(reverse('panel_profesor')).content.decode(), 'saldo')

    def test_la_tarjeta_lista_las_operaciones_con_importes_en_pesos(self):
        self.dictar(dar_paquete(self.ana, self.profe, 'intensivo'))
        self.compartir(self.paquete_con_videos(), 1)
        saldo = self.saldo()
        detalle = saldo[saldo.index('Detalle de liquidaciones'):]
        self.assertNotIn('Aún no has dictado clases', detalle)
        for esperado in ('Clase dictada', 'Video compartido', clp(18374), f'&minus;{clp(paquetes.comision(18374))}',
                         f'+{clp(paquetes.pago_profesor(18374))}', f'+{clp(3700)}'):
            self.assertIn(esperado, detalle)
        self.assertIn(self.ana.user.first_name, detalle)
        self.assertNotIn('desgloses_profesor', saldo)

    def test_sin_operaciones_lo_dice_con_palabras_claras(self):
        self.assertIn('Aún no has dictado clases ni compartido videos que sumen a tu saldo.', self.saldo())

    def test_si_hay_mas_de_las_que_se_muestran_lo_avisa(self):
        paquete = dar_paquete(self.ana, self.profe, 'intensivo')
        for dias in (-1, -2, -3):
            self.dictar(paquete, dias=dias)
        mostradas, total = detalle_liquidaciones.detalle(self.profe, maximo=2)
        with mock.patch.object(detalle_liquidaciones, 'detalle', return_value=(mostradas, total)):
            self.assertIn('Se muestran las 2 más recientes de 3.', self.saldo())

    def test_con_todas_a_la_vista_no_hay_aviso(self):
        self.dictar(dar_paquete(self.ana, self.profe, 'intensivo'))
        self.assertNotIn('más recientes de', self.saldo())

    def test_avisa_que_la_tabla_se_desliza_solo_si_hay_filas(self):
        """En celular los importes quedaban fuera de pantalla sin ninguna pista (visto en el navegador)."""
        self.assertNotIn('Desliza la tabla hacia los lados', self.saldo())
        self.dictar(dar_paquete(self.ana, self.profe, 'intensivo'))
        saldo = self.saldo()
        self.assertIn('id="tabla-liquidaciones"', saldo)
        self.assertIn('<p class="prof-nota-tabla prof-solo-celular">Desliza la tabla hacia los lados para ver los importes.</p>', saldo)
        self.assertLess(saldo.index('Desliza la tabla'), saldo.index('id="tabla-liquidaciones"'))  # sobre la tabla, no tras 21 filas

    def test_el_aviso_y_el_relleno_apretado_son_solo_de_celular(self):
        css = (settings.BASE_DIR / 'user_profesor/static/user_profesor/panel/06d_pulido_docente_tablas.css').read_text(encoding='utf-8')
        self.assertRegex(css, r'#portal-docente \.prof-solo-celular \{\s*display: none;')
        self.assertRegex(css, r'@media \(max-width: 640px\) \{\s*#portal-docente \.prof-solo-celular \{\s*display: block;')
        self.assertIn('#portal-docente #tabla-liquidaciones td', css)
