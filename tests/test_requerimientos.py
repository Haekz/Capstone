"""Registro de requerimientos de autoridad (E6, respuesta legal 02-nov): solo lideres, estados que solo avanzan y
nada se entrega sin verificar. Datos ficticios."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from requerimientos import gestion
from requerimientos.models import Entrega, Requerimiento
from tests.test_apoderados import crear_agente, entrar_soporte
from tests.test_retiros import crear_admin, entrar_admin

R = Requerimiento
HOY = timezone.localdate()


def datos(**cambios):
    return {'autoridad': 'Fiscalía Local de Providencia', 'referencia': 'RUC 2600123456-7',
            'recibido': HOY.isoformat(), 'vence': (HOY + timedelta(days=10)).isoformat(),
            'alcance': 'Registro de ingresos y pagos del ticket 123.', **cambios}


VERIFICAR = {'ok_identidad': 'on', 'ok_base_legal': 'on', 'ok_alcance': 'on',
             'verificacion': 'Oficio por correo institucional, confirmado por teléfono.'}
ENTREGA = {'datos': 'Fechas de ingreso y pagos del ticket 123.', 'medio': 'Oficio de respuesta',
           'destinatario': 'Fiscal a cargo, confirmado por la secretaría'}


class Base(TestCase):

    def setUp(self):
        self.lider = crear_agente('10000001-9', lider=True)
        entrar_soporte(self.client, self.lider)

    def registrar(self, **cambios):
        self.client.post(reverse('requerimiento_nuevo'), datos(**cambios))
        return R.objects.latest('pk')

    def accion(self, requerimiento, nombre, **post):
        return self.client.post(reverse('requerimiento_accion', args=[requerimiento.pk, nombre]), post)

    def verificado(self):
        requerimiento = self.registrar()
        self.accion(requerimiento, 'verificar', **VERIFICAR)
        requerimiento.refresh_from_db()
        return requerimiento


class PermisosTests(Base):

    def test_un_agente_comun_no_entra(self):
        entrar_soporte(self.client, crear_agente('10000002-7', 'otro'))
        for nombre in ('requerimientos', 'requerimiento_nuevo'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 302)

    def test_el_agente_comun_no_crea_ni_resuelve(self):
        requerimiento = self.registrar()
        entrar_soporte(self.client, crear_agente('10000002-7', 'otro'))
        self.assertEqual(self.client.post(reverse('requerimiento_nuevo'), datos()).status_code, 302)
        self.assertEqual(R.objects.count(), 1)
        self.assertEqual(self.client.get(reverse('requerimiento_detalle', args=[requerimiento.pk])).status_code, 302)
        self.assertEqual(self.accion(requerimiento, 'verificar', **VERIFICAR).status_code, 302)
        requerimiento.refresh_from_db()
        self.assertEqual(requerimiento.estado, R.RECIBIDO)

    def test_el_administrador_no_entra(self):
        requerimiento = self.registrar()
        admin, tutor = crear_admin()
        entrar_admin(self.client, admin, tutor)
        self.assertEqual(self.client.get(reverse('requerimientos')).status_code, 302)
        self.assertEqual(self.client.get(reverse('requerimiento_detalle', args=[requerimiento.pk])).status_code, 302)
        self.assertEqual(self.accion(requerimiento, 'rechazar', resolucion='x').status_code, 302)

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse('requerimientos'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_el_menu_del_lider_lo_muestra_y_el_del_agente_no(self):
        self.assertContains(self.client.get(reverse('panel_soporte')), reverse('requerimientos'))
        entrar_soporte(self.client, crear_agente('10000002-7', 'otro'))
        self.assertNotContains(self.client.get(reverse('panel_soporte')), reverse('requerimientos'))


class RegistrarTests(Base):

    def test_el_lider_lo_registra_y_queda_por_verificar(self):
        r = self.client.post(reverse('requerimiento_nuevo'), datos())
        requerimiento = R.objects.get()
        self.assertRedirects(r, reverse('requerimiento_detalle', args=[requerimiento.pk]), fetch_redirect_response=False)
        self.assertEqual((requerimiento.estado, requerimiento.registrado_por), (R.RECIBIDO, self.lider))
        self.assertEqual(requerimiento.autoridad, 'Fiscalía Local de Providencia')

    def test_el_plazo_no_puede_ser_anterior_a_la_recepcion(self):
        r = self.client.post(reverse('requerimiento_nuevo'), datos(vence=(HOY - timedelta(days=1)).isoformat()))
        self.assertContains(r, 'no puede ser anterior')
        self.assertFalse(R.objects.exists())

    def test_el_plazo_es_opcional(self):
        self.client.post(reverse('requerimiento_nuevo'), datos(vence=''))
        self.assertIsNone(R.objects.get().vence)

    def test_exige_autoridad_referencia_y_alcance(self):
        for campo in ('autoridad', 'referencia', 'alcance'):
            with self.subTest(campo=campo):
                self.client.post(reverse('requerimiento_nuevo'), datos(**{campo: ''}))
        self.assertFalse(R.objects.exists())

    def test_pide_no_copiar_datos_personales(self):
        self.assertContains(self.client.get(reverse('requerimiento_nuevo')), 'No copies nombres, RUT ni contenido')

    def test_la_lista_separa_abiertos_y_resueltos_y_marca_los_vencidos(self):
        self.registrar(referencia='ABIERTO-1', vence=(HOY - timedelta(days=1)).isoformat(), recibido=(HOY - timedelta(days=3)).isoformat())
        resuelto = self.registrar(referencia='RESUELTO-1', vence=(HOY - timedelta(days=1)).isoformat(), recibido=(HOY - timedelta(days=3)).isoformat())
        self.accion(resuelto, 'rechazar', resolucion='No es competente.')
        r = self.client.get(reverse('requerimientos'))
        self.assertContains(r, 'ABIERTO-1')
        self.assertContains(r, 'Vencido', count=1)  # el rechazado ya no cuenta como vencido
        self.assertContains(r, 'Abiertos (1)')
        self.assertContains(r, 'RESUELTO-1')


class VerificarTests(Base):

    def test_exige_los_tres_controles(self):
        requerimiento = self.registrar()
        for faltante in ('ok_identidad', 'ok_base_legal', 'ok_alcance'):
            with self.subTest(faltante=faltante):
                self.accion(requerimiento, 'verificar', **{k: v for k, v in VERIFICAR.items() if k != faltante})
                requerimiento.refresh_from_db()
                self.assertEqual(requerimiento.estado, R.RECIBIDO)

    def test_exige_decir_como_se_verifico(self):
        requerimiento = self.registrar()
        self.accion(requerimiento, 'verificar', **{**VERIFICAR, 'verificacion': '  '})
        requerimiento.refresh_from_db()
        self.assertEqual(requerimiento.estado, R.RECIBIDO)

    def test_verificado_deja_quien_cuando_y_como(self):
        requerimiento = self.verificado()
        self.assertEqual((requerimiento.estado, requerimiento.verificado_por), (R.VERIFICADO, self.lider))
        self.assertIsNotNone(requerimiento.verificado)
        self.assertIn('Oficio por correo institucional', requerimiento.verificacion)

    def test_no_se_verifica_dos_veces(self):
        requerimiento = self.verificado()
        r = self.accion(requerimiento, 'verificar', **VERIFICAR)
        self.assertEqual(r.status_code, 302)
        with self.assertRaises(gestion.RequerimientoError):
            gestion.verificar(self.lider, requerimiento, 'otra vez')


class EntregarTests(Base):

    def test_sin_verificar_no_se_entrega_nada(self):
        requerimiento = self.registrar()
        r = self.client.post(reverse('requerimiento_accion', args=[requerimiento.pk, 'entregar']), ENTREGA, follow=True)
        self.assertContains(r, 'está «recibido, por verificar»')
        self.assertFalse(Entrega.objects.exists())

    def test_verificado_registra_la_entrega_con_quien_y_cuando(self):
        requerimiento = self.verificado()
        self.accion(requerimiento, 'entregar', **ENTREGA)
        entrega = Entrega.objects.get()
        self.assertEqual((entrega.requerimiento, entrega.entregada_por, entrega.medio), (requerimiento, self.lider, 'Oficio de respuesta'))
        self.assertIsNotNone(entrega.fecha)
        self.assertContains(self.client.get(reverse('requerimiento_detalle', args=[requerimiento.pk])), 'Fiscal a cargo')

    def test_puede_haber_varias_entregas(self):
        requerimiento = self.verificado()
        self.accion(requerimiento, 'entregar', **ENTREGA)
        self.accion(requerimiento, 'entregar', **{**ENTREGA, 'datos': 'Segunda parte.'})
        self.assertEqual(requerimiento.entregas.count(), 2)

    def test_exige_todos_los_campos(self):
        requerimiento = self.verificado()
        for campo in ENTREGA:
            with self.subTest(campo=campo):
                self.accion(requerimiento, 'entregar', **{**ENTREGA, campo: ''})
        self.assertFalse(Entrega.objects.exists())

    def test_cerrado_o_rechazado_ya_no_recibe_entregas(self):
        for cierre in ('cerrar', 'rechazar'):
            with self.subTest(cierre=cierre):
                requerimiento = self.verificado()
                self.accion(requerimiento, cierre, resolucion='Listo.')
                self.accion(requerimiento, 'entregar', **ENTREGA)
                self.assertFalse(requerimiento.entregas.exists())


class CerrarYRechazarTests(Base):

    def test_cerrar_exige_estar_verificado(self):
        requerimiento = self.registrar()
        self.accion(requerimiento, 'cerrar', resolucion='Listo.')
        requerimiento.refresh_from_db()
        self.assertEqual(requerimiento.estado, R.RECIBIDO)

    def test_cerrar_deja_el_resumen_quien_y_cuando(self):
        requerimiento = self.verificado()
        self.accion(requerimiento, 'entregar', **ENTREGA)
        self.accion(requerimiento, 'cerrar', resolucion='Se respondió el oficio.')
        requerimiento.refresh_from_db()
        self.assertEqual((requerimiento.estado, requerimiento.resuelto_por, requerimiento.resolucion),
                         (R.CERRADO, self.lider, 'Se respondió el oficio.'))
        self.assertIsNotNone(requerimiento.resuelto)

    def test_se_puede_rechazar_antes_y_despues_de_verificar(self):
        for preparar in (self.registrar, self.verificado):
            with self.subTest(preparar=preparar.__name__):
                requerimiento = preparar()
                self.accion(requerimiento, 'rechazar', resolucion='No es competente.')
                requerimiento.refresh_from_db()
                self.assertEqual((requerimiento.estado, requerimiento.resolucion), (R.RECHAZADO, 'No es competente.'))

    def test_rechazar_exige_el_motivo(self):
        requerimiento = self.registrar()
        self.accion(requerimiento, 'rechazar', resolucion='')
        requerimiento.refresh_from_db()
        self.assertEqual(requerimiento.estado, R.RECIBIDO)

    def test_los_estados_solo_avanzan(self):
        for cierre in ('cerrar', 'rechazar'):
            with self.subTest(cierre=cierre):
                requerimiento = self.verificado()
                self.accion(requerimiento, cierre, resolucion='Listo.')
                estado = R.objects.get(pk=requerimiento.pk).estado
                for nombre, post in (('verificar', VERIFICAR), ('cerrar', {'resolucion': 'x'}), ('rechazar', {'resolucion': 'x'})):
                    self.accion(requerimiento, nombre, **post)
                self.assertEqual(R.objects.get(pk=requerimiento.pk).estado, estado)


class DetalleTests(Base):

    def test_ofrece_solo_las_acciones_del_estado(self):
        requerimiento = self.registrar()
        url = reverse('requerimiento_detalle', args=[requerimiento.pk])
        r = self.client.get(url)
        self.assertContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'verificar']))
        self.assertContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'rechazar']))
        self.assertNotContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'entregar']))
        self.assertNotContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'cerrar']))
        self.accion(requerimiento, 'verificar', **VERIFICAR)
        r = self.client.get(url)
        self.assertContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'entregar']))
        self.assertContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'cerrar']))
        self.assertNotContains(r, reverse('requerimiento_accion', args=[requerimiento.pk, 'verificar']))

    def test_resuelto_no_ofrece_ninguna_accion(self):
        requerimiento = self.registrar()
        self.accion(requerimiento, 'rechazar', resolucion='No es competente.')
        r = self.client.get(reverse('requerimiento_detalle', args=[requerimiento.pk]))
        self.assertContains(r, 'No es competente.')
        self.assertNotContains(r, '/requerimientos/%d/' % requerimiento.pk + 'verificar')
        self.assertNotContains(r, '<form method="post" action')

    def test_accion_desconocida_es_404_y_se_exige_post(self):
        requerimiento = self.registrar()
        self.assertEqual(self.accion(requerimiento, 'borrar').status_code, 404)
        self.assertEqual(self.client.get(reverse('requerimiento_accion', args=[requerimiento.pk, 'verificar'])).status_code, 405)

    def test_no_guarda_las_casillas_de_control(self):
        campos = {f.name for f in R._meta.get_fields()}
        self.assertFalse({c for c in campos if c.startswith('ok_')})

    def test_un_requerimiento_inexistente_es_404(self):
        self.assertEqual(self.client.get(reverse('requerimiento_detalle', args=[999])).status_code, 404)
