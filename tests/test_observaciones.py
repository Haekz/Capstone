"""Observaciones del profesor sobre clases ya realizadas (el feedback docente de Mi Progreso). Datos ficticios.

Reglas: solo el profesor de esa clase, solo si ya se hizo, una por clase y sin datos de contacto. Las lee el alumno
adulto en su Mi Progreso; las del menor las lee su apoderado, no el menor. Se borran con la cuenta del alumno.
"""

from io import StringIO

from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from alumnos.models import Inscripcion, SesionClase
from apoderados.models import Apoderado
from observaciones.models import Observacion
from supresiones.datos_propios import limpiar
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_BETO, RUT_PROFE, Escenario
from tests.test_suscripciones import dar_plan

TEXTO = 'Buen avance con las ecuaciones; practica los problemas de la guía.'
RUT_MENOR = '77777777-7'  # el RUT por defecto de crear_menor_vinculado choca con el de Beto


def inscribir(alumno, clase, dias, estado=Inscripcion.ESTADO_CONFIRMADA):
    return Inscripcion.objects.create(alumno=alumno, clase=clase, sesion=crear_sesion(clase, dias=dias), estado=estado)


class ProfesorDejaObservacionTests(Escenario):

    def setUp(self):
        self.hecha = inscribir(self.ana, self.clase, -2)
        self.entrar(RUT_PROFE)

    def guardar(self, inscripcion=None, texto=TEXTO):
        return self.client.post(reverse('observacion_guardar', args=[(inscripcion or self.hecha).pk]), {'texto': texto})

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]

    def test_guarda_y_vuelve_a_su_panel(self):
        respuesta = self.guardar()
        self.assertRedirects(respuesta, reverse('panel_profesor'), fetch_redirect_response=False)
        self.assertEqual(Observacion.objects.get().texto, TEXTO)
        self.assertEqual(self.mensajes(respuesta), ['Observación guardada.'])

    def test_es_una_por_clase_y_se_puede_corregir(self):
        self.guardar()
        self.guardar(texto='Corrijo: va muy bien, sigue con la guía de factorización.')
        self.assertEqual(Observacion.objects.get().texto, 'Corrijo: va muy bien, sigue con la guía de factorización.')

    def test_solo_de_clases_ya_realizadas(self):
        casos = {
            'futura': inscribir(self.ana, self.clase, 2),
            'pendiente': inscribir(self.ana, self.clase, -3, Inscripcion.ESTADO_PENDIENTE),
            'cancelada': inscribir(self.ana, self.clase, -4, Inscripcion.ESTADO_CANCELADA),
        }
        sesion_cancelada = inscribir(self.ana, self.clase, -5)
        SesionClase.objects.filter(pk=sesion_cancelada.sesion_id).update(estado=SesionClase.ESTADO_CANCELADA)
        casos['sesion cancelada'] = sesion_cancelada
        for nombre, inscripcion in casos.items():
            with self.subTest(clase=nombre):
                self.assertEqual(self.guardar(inscripcion).status_code, 404)
        self.assertFalse(Observacion.objects.exists())

    def test_solo_de_sus_propias_clases(self):
        ajena = inscribir(self.ana, self.clase_otro, -2)
        self.assertEqual(self.guardar(ajena).status_code, 404)
        self.assertFalse(Observacion.objects.exists())

    def test_rechaza_lo_corto_lo_largo_y_los_datos_de_contacto(self):
        casos = {
            'corto': ('Bien.', 'al menos 10'),
            'largo': ('a' * 501, '500'),
            'telefono': ('Llámame al +56 9 8765 4321 para seguir.', 'No puedes compartir'),
            'correo': ('Escríbeme a profe@correo.cl y vemos la guía.', 'No puedes compartir'),
        }
        for nombre, (texto, aviso) in casos.items():
            with self.subTest(texto=nombre):
                respuesta = self.guardar(texto=texto)
                self.assertRedirects(respuesta, reverse('panel_profesor'), fetch_redirect_response=False)
                self.assertIn(aviso, self.mensajes(respuesta)[-1])  # los de antes siguen en el almacenamiento
        self.assertFalse(Observacion.objects.exists())

    def test_solo_por_post_y_solo_el_profesor(self):
        url = reverse('observacion_guardar', args=[self.hecha.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.entrar(RUT_ANA)
        self.assertNotEqual(self.client.post(url, {'texto': TEXTO}).status_code, 200)
        self.assertFalse(Observacion.objects.exists())

    def test_el_panel_lista_las_clases_realizadas_con_su_observacion_y_solo_nombre_de_pila(self):
        self.guardar()
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, f'id="obs-{self.hecha.pk}"')
        self.assertContains(r, TEXTO)
        self.assertContains(r, 'la lee el alumno')
        self.assertContains(r, f'Algebra con {self.ana.user.first_name}')
        self.assertNotContains(r, RUT_ANA)

    def test_sin_clases_realizadas_el_panel_lo_dice(self):
        self.hecha.delete()
        self.assertContains(self.client.get(reverse('panel_profesor')), 'podrás dejar aquí tu observación')

    def test_la_del_menor_dice_que_la_lee_su_apoderado(self):
        menor = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR).alumno
        inscribir(menor, self.clase, -3)
        self.assertContains(self.client.get(reverse('panel_profesor')), 'la lee su apoderado')


class QuienLeeTests(Escenario):

    def setUp(self):
        self.hecha = inscribir(self.ana, self.clase, -2)
        dar_plan(self.ana)  # Mi Progreso es premium: sin plan no se renderiza
        Observacion.objects.create(inscripcion=self.hecha, texto=TEXTO)

    def test_el_alumno_adulto_ve_la_suya_con_el_nombre_del_profesor(self):
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, f'«{TEXTO}»')
        self.assertContains(r, self.profe.nombre)
        self.assertNotContains(r, 'Aún no hay observaciones')
        self.assertNotContains(r, 'teacherFeedback')
        self.assertNotContains(r, 'los comentarios de docentes aún no se registran')

    def test_no_ve_las_de_otro_alumno(self):
        dar_plan(self.beto)
        self.entrar(RUT_BETO)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertNotContains(r, TEXTO)
        self.assertContains(r, 'Aún no hay observaciones')

    def test_el_texto_se_escapa(self):
        Observacion.objects.update(texto='<script>alert(1)</script> practica la guía')
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(r, '<script>alert(1)</script>')

    def test_el_menor_no_la_ve_en_su_cuenta_pero_su_apoderado_si(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        vinculo = crear_menor_vinculado(apoderado, rut=RUT_MENOR)
        menor = vinculo.alumno
        dar_plan(menor)
        Observacion.objects.create(inscripcion=inscribir(menor, self.clase, -3), texto='Trabajó muy bien las fracciones.')

        entrar(self.client, menor.user, alumno_id=menor.id_alumno)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertNotContains(r, 'Trabajó muy bien las fracciones.')
        self.assertContains(r, 'Las observaciones de tus profesores las recibe tu apoderado')

        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)
        r = self.client.get(reverse('apoderado_clases_estudiante', args=[vinculo.pk]))
        self.assertContains(r, 'Trabajó muy bien las fracciones.')
        self.assertNotContains(r, TEXTO)  # la de Ana es de otra persona

    def test_un_apoderado_sin_vinculo_con_el_menor_no_la_ve(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        otro = crear_apoderado('15151515-1', Apoderado.VERIFICADO)
        entrar(self.client, otro.user, apoderado_id=otro.id_apoderado)
        self.assertEqual(self.client.get(reverse('apoderado_clases_estudiante', args=[vinculo.pk])).status_code, 404)


class SupresionTests(Escenario):

    def test_al_eliminar_la_cuenta_del_alumno_se_borran_sus_observaciones_y_solo_las_suyas(self):
        suya = Observacion.objects.create(inscripcion=inscribir(self.ana, self.clase, -2), texto=TEXTO)
        ajena = Observacion.objects.create(inscripcion=inscribir(self.beto, self.clase, -2), texto=TEXTO)
        limpiar(self.ana.user)
        self.assertEqual(list(Observacion.objects.all()), [ajena])
        self.assertFalse(Observacion.objects.filter(pk=suya.pk).exists())


class ConservacionTests(Escenario):
    """Pasados OBSERVACIONES_MESES (12) desde la clase, la observacion ya no se escribe, no se ve y se borra."""

    def setUp(self):
        self.vieja = inscribir(self.ana, self.clase, -400)  # mas de 12 meses
        self.reciente = inscribir(self.ana, self.clase, -300)  # menos de 12, mas de 6
        for inscripcion in (self.vieja, self.reciente):
            Observacion.objects.create(inscripcion=inscripcion, texto=TEXTO)

    def borrar(self):
        salida = StringIO()
        call_command('borrar_observaciones_vencidas', stdout=salida)
        return salida.getvalue()

    def test_el_comando_borra_solo_las_vencidas(self):
        self.assertIn('borradas por vencidas: 1', self.borrar())
        self.assertEqual(list(Observacion.objects.values_list('inscripcion_id', flat=True)), [self.reciente.pk])
        self.assertIn('borradas por vencidas: 0', self.borrar())  # idempotente

    def test_el_plazo_sale_de_la_configuracion(self):
        with override_settings(OBSERVACIONES_MESES=6):
            self.assertIn('borradas por vencidas: 2', self.borrar())
        self.assertFalse(Observacion.objects.exists())

    def test_una_clase_vencida_ya_no_admite_observacion_ni_se_lista_al_profesor(self):
        self.entrar(RUT_PROFE)
        self.assertEqual(self.client.post(reverse('observacion_guardar', args=[self.vieja.pk]), {'texto': TEXTO}).status_code,
                         404)
        panel = self.client.get(reverse('panel_profesor'))
        self.assertContains(panel, f'id="obs-{self.reciente.pk}"')
        self.assertNotContains(panel, f'id="obs-{self.vieja.pk}"')

    def test_el_alumno_no_ve_una_vencida_aunque_el_cron_no_haya_corrido(self):
        Observacion.objects.filter(inscripcion=self.vieja).update(texto='Texto de la vencida, no debe verse.')
        dar_plan(self.ana)
        self.entrar(RUT_ANA)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertNotContains(r, 'Texto de la vencida')
        self.assertContains(r, TEXTO)

    def test_el_aviso_dice_el_plazo_real(self):
        dar_plan(self.ana)
        self.entrar(RUT_ANA)
        self.assertContains(self.client.get(reverse('alumno_pag1')), 'Se eliminan 12 meses después de la clase.')
        Observacion.objects.create(inscripcion=inscribir(self.ana, self.clase, -5), texto=TEXTO)  # visible aun con 1 mes
        with override_settings(OBSERVACIONES_MESES=1):
            self.assertContains(self.client.get(reverse('alumno_pag1')), 'Se eliminan 1 mes después de la clase.')
        self.entrar(RUT_PROFE)
        self.assertContains(self.client.get(reverse('panel_profesor')), 'Se eliminan 12 meses después de la clase.')
