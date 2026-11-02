"""El profesor y soporte frente a las conversaciones de apoderados (paso C2b, decidido 02-nov). Datos ficticios."""

from django.urls import reverse

from alumnos.models import Inscripcion
from alumnos.services import InscripcionService
from apoderados.models import Apoderado, Vinculo
from mensajes import servicio
from mensajes.models import Conversacion, ReporteConversacion
from soporte.models import Ticket
from tests.test_agenda_cancelar import EN_13_HORAS
from tests.test_apoderados import RUT, crear_agente, crear_apoderado, entrar, entrar_soporte
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_PROFE, Escenario, dar_paquete

RUT_MENOR = '77777777-7'
RUT_OTRO_APODERADO = '99999999-9'


class ProfesorYApoderadosTests(Escenario):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut=RUT_MENOR)
        self.menor = self.vinculo.alumno
        dar_paquete(self.menor, self.profe)
        self.inscripcion = InscripcionService.inscribir_alumno_en_sesion(
            self.menor, crear_sesion(self.clase, dias=EN_13_HORAS, cupo=1).pk, vinculo=self.vinculo)
        self.entrar(RUT_PROFE)

    def abrir(self):
        return self.client.post(reverse('mensajes_profesor_abrir', args=[self.inscripcion.pk]))

    def otro_apoderado(self):
        """Segundo apoderado verificado del mismo menor (madre y padre)."""
        apoderado = crear_apoderado(RUT_OTRO_APODERADO, Apoderado.VERIFICADO)
        return Vinculo.objects.create(apoderado=apoderado, alumno=self.menor, parentesco='padre',
                                      estado=Vinculo.VERIFICADO, version_declaracion=self.vinculo.version_declaracion,
                                      declaracion_aceptada=self.vinculo.declaracion_aceptada)

    # --- Mi Agenda ---

    def test_abre_la_conversacion_con_el_apoderado_y_lleva_al_buzon(self):
        r = self.abrir()
        conversacion = Conversacion.objects.get()
        self.assertRedirects(r, f"{reverse('panel_profesor')}?c={conversacion.pk}", fetch_redirect_response=False)
        self.assertEqual((conversacion.alumno, conversacion.cliente), (self.menor, self.apoderado.user))

    def test_con_dos_apoderados_abre_una_conversacion_con_cada_uno_y_avisa(self):
        self.otro_apoderado()
        r = self.abrir()
        self.assertEqual(Conversacion.objects.count(), 2)
        self.assertEqual(Conversacion.objects.filter(alumno=self.menor).values('cliente').distinct().count(), 2)
        self.assertContains(self.client.get(r.url), 'más de un apoderado')

    def test_sin_apoderado_con_vinculo_activo_se_explica_y_no_se_crea(self):
        self.vinculo.revocar(self.apoderado.user, 'ya no soy apoderado')
        r = self.client.post(reverse('mensajes_profesor_abrir', args=[self.inscripcion.pk]), follow=True)
        self.assertContains(r, 'no tiene un apoderado con vínculo activo')
        self.assertFalse(Conversacion.objects.exists())

    def test_no_abre_con_la_reserva_de_otro_profesor(self):
        ajena = Inscripcion.objects.create(alumno=self.menor, clase=self.clase_otro,
                                           sesion=crear_sesion(self.clase_otro, dias=EN_13_HORAS, cupo=1))
        r = self.client.post(reverse('mensajes_profesor_abrir', args=[ajena.pk]))
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Conversacion.objects.exists())

    # --- Buzon del profesor ---

    def test_dos_apoderados_aparecen_como_dos_conversaciones_del_mismo_estudiante(self):
        self.otro_apoderado()
        self.abrir()
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, f'Apoderado de {self.menor.user.first_name}', count=2)

    def test_con_el_vinculo_vigente_el_profesor_ve_el_formulario(self):
        self.abrir()
        r = self.client.get(reverse('panel_profesor'), {'c': Conversacion.objects.get().pk})
        self.assertContains(r, reverse('mensajes_profesor_enviar', args=[Conversacion.objects.get().pk]))
        self.assertNotContains(r, 'solo para lectura')

    def test_con_el_vinculo_terminado_el_profesor_lee_pero_no_escribe(self):
        self.abrir()
        conversacion = Conversacion.objects.get()
        self.vinculo.revocar(self.apoderado.user, 'ya no soy apoderado')
        r = self.client.get(reverse('panel_profesor'), {'c': conversacion.pk})
        self.assertContains(r, 'solo para lectura')
        self.assertNotContains(r, reverse('mensajes_profesor_enviar', args=[conversacion.pk]))
        r = self.client.post(reverse('mensajes_profesor_enviar', args=[conversacion.pk]), {'texto': 'Hola'}, follow=True)
        self.assertContains(r, 'solo para lectura')

    # --- Reportar y soporte ---

    def test_el_apoderado_reporta_desde_su_pagina_y_vuelve_a_ella(self):
        crear_agente('10000001-9', Ticket.CONDUCTA)
        self.abrir()
        conversacion = Conversacion.objects.get()
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)
        url = reverse('mensajes_reportar', args=[conversacion.pk])
        self.assertContains(self.client.get(url), f"{reverse('mensajes_apoderado')}?c={conversacion.pk}")
        r = self.client.post(url, {'descripcion': 'Me incomoda.'})
        self.assertRedirects(r, reverse('mis_tickets'), fetch_redirect_response=False)
        self.assertEqual(ReporteConversacion.objects.get().ticket.estudiante, self.menor)

    def test_soporte_la_lee_con_las_etiquetas_de_apoderado(self):
        agente = crear_agente('10000001-9', Ticket.CONDUCTA)
        self.abrir()
        conversacion = Conversacion.objects.get()
        servicio.enviar(self.apoderado.user, conversacion, 'Hola profe')
        reporte = servicio.reportar(self.profe.user, conversacion, 'Algo raro.')
        entrar_soporte(self.client, agente)
        r = self.client.get(reverse('mensajes_soporte_leer', args=[reporte.ticket_id]))
        self.assertContains(r, f'Apoderado de {self.menor.user.first_name}')
        self.assertContains(r, '(apoderado)')
        self.assertContains(r, 'Hola profe')
