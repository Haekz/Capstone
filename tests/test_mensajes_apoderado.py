"""Mensajes del apoderado con el profesor de su estudiante menor (paso C2a, decidido 02-nov). Datos ficticios."""

from django.urls import reverse

from apoderados.models import Apoderado
from mensajes import servicio
from mensajes.models import Conversacion, Mensaje
from mensajes.servicio import MensajeError
from notificaciones.models import Notificacion
from soporte.models import Ticket
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado, hace_anios
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete

RUT_MENOR = '77777777-7'
RUT_OTRO_APODERADO = '99999999-9'


class MensajesDelApoderadoTests(Escenario):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.menor = self.vinculo.alumno
        self.nombre_menor = self.menor.user.first_name
        dar_paquete(self.menor, self.profe)
        self.entrar_apoderado(self.apoderado)

    def entrar_apoderado(self, apoderado):
        entrar(self.client, apoderado.user, apoderado_id=apoderado.id_apoderado)

    def buzon(self, **params):
        return self.client.get(reverse('mensajes_apoderado'), params)

    def abrir(self):
        self.client.post(reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.profe.pk]))
        self.conversacion = Conversacion.objects.get()

    def conversar(self, autor, texto):
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(autor, self.conversacion, texto)

    # --- abrir ---

    def test_ofrece_escribir_a_los_profesores_del_estudiante_y_a_nadie_mas(self):
        r = self.buzon()
        self.assertContains(r, reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.profe.pk]))
        self.assertContains(r, f'sobre {self.nombre_menor}')
        self.assertNotContains(r, reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.otro.pk]))

    def test_abrir_crea_la_conversacion_del_apoderado_y_lleva_al_buzon(self):
        r = self.client.post(reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.profe.pk]))
        conversacion = Conversacion.objects.get()
        self.assertRedirects(r, f"{reverse('mensajes_apoderado')}?c={conversacion.pk}", fetch_redirect_response=False)
        self.assertEqual((conversacion.alumno, conversacion.profesor, conversacion.cliente),
                         (self.menor, self.profe, self.apoderado.user))
        self.assertTrue(conversacion.es_de_apoderado)

    def test_abrirla_dos_veces_no_duplica(self):
        self.abrir()
        self.abrir()
        self.assertEqual(Conversacion.objects.count(), 1)

    def test_sin_clase_ni_paquete_con_ese_profesor_se_explica_y_no_se_crea(self):
        r = self.client.post(reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.otro.pk]), follow=True)
        self.assertContains(r, 'Solo pueden escribirse quienes tienen una clase reservada o un paquete activo')
        self.assertFalse(Conversacion.objects.exists())

    def test_con_el_vinculo_de_otro_apoderado_da_404(self):
        otro = crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO)
        self.entrar_apoderado(otro)
        r = self.client.post(reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.profe.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Conversacion.objects.exists())

    # --- enviar y avisos ---

    def test_enviar_guarda_y_vuelve_a_la_conversacion(self):
        self.abrir()
        r = self.client.post(reverse('mensajes_apoderado_enviar', args=[self.conversacion.pk]),
                             {'texto': 'Hola profe, ¿vemos la clase del martes?'})
        self.assertRedirects(r, f"{reverse('mensajes_apoderado')}?c={self.conversacion.pk}", fetch_redirect_response=False)
        self.assertEqual(Mensaje.objects.get().autor, self.apoderado.user)

    def test_un_contacto_se_bloquea_y_se_explica(self):
        self.abrir()
        r = self.client.post(reverse('mensajes_apoderado_enviar', args=[self.conversacion.pk]),
                             {'texto': 'llamame al 987654321'}, follow=True)
        self.assertContains(r, 'No puedes compartir un teléfono por aquí')
        self.assertFalse(Mensaje.objects.exists())

    def test_el_aviso_al_profesor_no_lleva_el_nombre_del_apoderado(self):
        self.abrir()
        self.conversar(self.apoderado.user, 'Hola profe')
        aviso = Notificacion.objects.get(usuario=self.profe.user)
        self.assertEqual(aviso.texto, f'Apoderado de {self.nombre_menor} te escribió un mensaje.')
        self.assertNotIn(self.apoderado.user.first_name, aviso.texto)
        self.assertEqual(aviso.enlace, f"{reverse('panel_profesor')}?c={self.conversacion.pk}")

    def test_el_aviso_al_apoderado_dice_de_que_estudiante_y_lleva_a_su_pagina(self):
        self.abrir()
        self.conversar(self.profe.user, 'Hola, soy el profe')
        aviso = Notificacion.objects.get(usuario=self.apoderado.user)
        self.assertEqual(aviso.texto, f'{self.profe.user.first_name} te escribió un mensaje sobre {self.nombre_menor}.')
        self.assertEqual(aviso.enlace, f"{reverse('mensajes_apoderado')}?c={self.conversacion.pk}")

    def test_lo_nuevo_del_profesor_sale_sin_leer_hasta_abrirlo(self):
        self.abrir()
        self.conversar(self.profe.user, 'Hola')
        self.assertContains(self.buzon(), 'Mensajes sin leer')
        self.assertContains(self.buzon(c=self.conversacion.pk), 'Hola')
        self.assertNotContains(self.buzon(), 'Mensajes sin leer')

    def test_otro_apoderado_no_puede_escribir_en_la_conversacion(self):
        self.abrir()
        self.entrar_apoderado(crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO))
        r = self.client.post(reverse('mensajes_apoderado_enviar', args=[self.conversacion.pk]), {'texto': 'Hola'})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Mensaje.objects.exists())

    def test_la_conversacion_de_otro_apoderado_no_se_ve(self):
        self.abrir()
        self.conversar(self.profe.user, 'Mensaje privado para el apoderado de uno')
        self.entrar_apoderado(crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO))
        self.assertNotContains(self.buzon(c=self.conversacion.pk), 'Mensaje privado')

    # --- lo que ve el profesor ---

    def test_el_profesor_ve_apoderado_de_el_menor_y_nada_mas_del_apoderado(self):
        self.abrir()
        self.conversar(self.apoderado.user, 'Hola profe')
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'), {'c': self.conversacion.pk})
        self.assertContains(r, f'Apoderado de {self.nombre_menor}')
        for privado in (self.apoderado.user.first_name, self.apoderado.user.email, self.apoderado.user.rut):
            self.assertNotContains(r, privado)

    # --- solo lectura ---

    def test_con_el_vinculo_revocado_se_lee_pero_no_se_escribe(self):
        self.abrir()
        self.conversar(self.profe.user, 'Mensaje anterior')
        self.vinculo.revocar(self.apoderado.user, 'ya no soy apoderado')
        r = self.buzon(c=self.conversacion.pk)
        self.assertContains(r, 'Mensaje anterior')
        self.assertContains(r, 'solo para lectura')
        self.assertNotContains(r, reverse('mensajes_apoderado_enviar', args=[self.conversacion.pk]))
        r = self.client.post(reverse('mensajes_apoderado_enviar', args=[self.conversacion.pk]), {'texto': 'Hola'}, follow=True)
        self.assertContains(r, 'solo para lectura')
        self.assertEqual(Mensaje.objects.count(), 1)

    def test_con_el_vinculo_revocado_el_profesor_tampoco_puede_escribir(self):
        self.abrir()
        self.vinculo.revocar(self.apoderado.user, 'ya no soy apoderado')
        with self.assertRaisesMessage(MensajeError, 'solo para lectura'):
            servicio.enviar(self.profe.user, self.conversacion, 'Hola')

    def test_con_el_vinculo_revocado_no_se_abre_una_conversacion_nueva(self):
        self.vinculo.revocar(self.apoderado.user, 'ya no soy apoderado')
        with self.assertRaises(MensajeError):
            servicio.abrir_conversacion_de_apoderado(self.vinculo, self.profe)

    def test_con_el_apoderado_rechazado_queda_solo_lectura(self):
        self.abrir()
        Apoderado.objects.filter(pk=self.apoderado.pk).update(estado=Apoderado.RECHAZADO)
        self.assertTrue(servicio.es_solo_lectura(Conversacion.objects.get()))

    def test_al_cumplir_18_la_del_apoderado_queda_solo_lectura_y_el_estudiante_abre_la_suya(self):
        self.abrir()
        self.menor.user.fecha_nacimiento = hace_anios(19)
        self.menor.user.save()
        self.assertTrue(servicio.es_solo_lectura(Conversacion.objects.get()))
        propia = servicio.abrir_conversacion(self.menor, self.profe)
        self.assertEqual(propia.cliente, self.menor.user)
        self.assertEqual(Conversacion.objects.count(), 2)
        self.assertFalse(servicio.es_solo_lectura(propia))

    def test_la_conversacion_de_un_alumno_adulto_nunca_es_solo_lectura(self):
        dar_paquete(self.ana, self.profe)
        self.assertFalse(servicio.es_solo_lectura(servicio.abrir_conversacion(self.ana, self.profe)))

    # --- reportar y portal ---

    def test_el_apoderado_reporta_por_su_estudiante(self):
        crear_agente('10000001-9', Ticket.CONDUCTA)
        self.abrir()
        reporte = servicio.reportar(self.apoderado.user, self.conversacion, 'Me incomoda.')
        self.assertEqual(reporte.ticket.estudiante, self.menor)
        self.assertEqual(reporte.ticket.autor, self.apoderado.user)

    def test_el_profesor_que_reporta_no_marca_estudiante(self):
        crear_agente('10000001-9', Ticket.CONDUCTA)
        self.abrir()
        self.assertIsNone(servicio.reportar(self.profe.user, self.conversacion, 'Me incomoda.').ticket.estudiante)

    def test_el_portal_del_apoderado_enlaza_a_los_mensajes(self):
        self.assertContains(self.client.get(reverse('portal_apoderado')), reverse('mensajes_apoderado'))

    def test_un_alumno_no_entra_a_los_mensajes_del_apoderado(self):
        self.entrar(self.ana.user.rut)
        self.assertNotEqual(self.client.get(reverse('mensajes_apoderado')).status_code, 200)
