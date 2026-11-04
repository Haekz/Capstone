"""Eliminar la cuenta por pedido del usuario (respuesta legal del 02-nov, E3): evaluacion por categoria,
identidad por enlace al correo, constancia y limites. Datos ficticios."""

import re
from datetime import timedelta
from unittest import mock

from django.core import mail, signing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from alumnos.models import Alumno, Inscripcion
from mensajes import servicio
from soporte.models import Ticket
from soporte.tickets import abrir_reporte, agregar_mensaje
from supresiones import evaluacion, identidad, solicitud
from supresiones.models import SolicitudSupresion
from tests.test_apoderados import User, crear_agente, entrar
from tests.test_apoderados_vinculos import hace_anios
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_BETO, RUT_PROFE, Escenario, dar_paquete
from tests.test_retiros import crear_admin

ENLACE = re.compile(r'https?://[^/\s]+(/privacidad/eliminar-cuenta/confirmar/\S+/)')


def nombres(ev):
    return [c.nombre for c in ev.categorias]


class EvaluacionTests(Escenario):

    def test_sin_historial_solo_se_eliminan_los_datos_de_la_cuenta(self):
        ev = evaluacion.evaluar(self.beto.user)
        self.assertEqual(nombres(ev), ['Datos de la cuenta'])
        self.assertTrue(ev.puede)
        self.assertFalse(ev.conserva_algo)

    def test_un_paquete_con_clases_sin_usar_impide_eliminar_y_los_pagos_se_conservan(self):
        dar_paquete(self.ana, self.profe)
        ev = evaluacion.evaluar(self.ana.user)
        self.assertFalse(ev.puede)
        self.assertIn('sin usar', ev.bloqueos[0])
        self.assertIn('Pagos y clases', nombres(ev))
        self.assertIn('Tickets de soporte', nombres(ev))  # la cuenta quedaria seudonimizada

    def test_un_paquete_ya_usado_no_impide_pero_se_conserva(self):
        paquete = dar_paquete(self.ana, self.profe, plan='flexible')  # una sola clase
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase, sesion=crear_sesion(self.clase, -3), paquete=paquete)
        ev = evaluacion.evaluar(self.ana.user)
        self.assertTrue(ev.puede)
        self.assertIn('Pagos y clases', nombres(ev))

    def test_un_paquete_vencido_no_impide(self):
        dar_paquete(self.ana, self.profe, dias=-1)
        self.assertTrue(evaluacion.evaluar(self.ana.user).puede)

    def test_una_clase_reservada_por_dictar_impide(self):
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=crear_sesion(self.clase, 3))
        ev = evaluacion.evaluar(self.beto.user)
        self.assertFalse(ev.puede)
        self.assertIn('por dictar', ev.bloqueos[0])

    def test_otro_ticket_abierto_impide_pero_no_el_de_la_propia_solicitud(self):
        crear_agente('10000001-9', Ticket.OTRO, Ticket.PRIVACIDAD)
        abrir_reporte(self.beto.user, Ticket.OTRO, 'Otra cosa', 'Algo')
        self.assertFalse(evaluacion.evaluar(self.beto.user).puede)
        propio = abrir_reporte(self.ana.user, Ticket.PRIVACIDAD, 'Eliminar mi cuenta', 'x')
        self.assertTrue(evaluacion.evaluar(self.ana.user, propio).puede)

    def test_una_conversacion_reportada_se_conserva_solo_para_soporte(self):
        crear_agente('10000002-7', Ticket.CONDUCTA)
        dar_paquete(self.beto, self.profe)
        conversacion = servicio.abrir_conversacion(self.beto, self.profe)
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(self.beto.user, conversacion, 'Hola')
        servicio.reportar(self.profe.user, conversacion, 'Me incomoda.')
        ev = evaluacion.evaluar(self.beto.user)
        self.assertIn('Conversaciones reportadas', nombres(ev))
        self.assertNotIn('Conversaciones con profesores', nombres(ev))  # la unica es la reportada

    def test_las_conversaciones_normales_se_eliminan(self):
        dar_paquete(self.beto, self.profe)
        servicio.abrir_conversacion(self.beto, self.profe)
        self.assertIn('Conversaciones con profesores', nombres(evaluacion.evaluar(self.beto.user)))

    def test_una_cuenta_de_administrador_no_se_elimina_desde_aqui(self):
        admin, _ = crear_admin()
        ev = evaluacion.evaluar(admin)
        self.assertFalse(ev.puede)
        self.assertEqual(ev.categorias, ())
        self.assertIn('no se elimina desde aquí', ev.bloqueos[0])


class SolicitarTests(Escenario):

    def setUp(self):
        self.agente = crear_agente('10000001-9', Ticket.PRIVACIDAD)
        self.entrar(RUT_BETO)

    def pedir_enlace(self):
        self.client.post(reverse('eliminar_cuenta'), {'entiendo': 'on'})
        return ENLACE.search(mail.outbox[-1].body).group(1)

    def confirmar(self, enlace, **datos):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(enlace, datos or {'confirmo': 'on'})

    def test_la_pagina_explica_que_se_elimina_y_que_se_conserva(self):
        r = self.client.get(reverse('eliminar_cuenta'))
        self.assertContains(r, 'Qué se elimina y qué se conserva')
        self.assertContains(r, 'Datos de la cuenta')
        self.assertContains(r, '10 días hábiles')

    def test_pide_un_enlace_al_correo_registrado_sin_abrir_la_solicitud(self):
        self.pedir_enlace()
        self.assertEqual(mail.outbox[-1].to, [self.beto.user.email])
        self.assertFalse(SolicitudSupresion.objects.exists())
        self.assertFalse(Ticket.objects.exists())

    def test_sin_marcar_la_casilla_no_se_envia_nada(self):
        r = self.client.post(reverse('eliminar_cuenta'), {})
        self.assertContains(r, 'Marca la casilla')
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_correo_registrado_no_se_puede_verificar(self):
        User.objects.filter(pk=self.beto.user_id).update(email='')
        r = self.client.post(reverse('eliminar_cuenta'), {'entiendo': 'on'}, follow=True)
        self.assertContains(r, 'No tenemos un correo registrado')
        self.assertEqual(len(mail.outbox), 0)

    def test_abrir_el_enlace_solo_pregunta_no_crea_la_solicitud(self):
        r = self.client.get(self.pedir_enlace())
        self.assertContains(r, 'Confirmar que quieres eliminar tu cuenta')
        self.assertFalse(SolicitudSupresion.objects.exists())

    def test_confirmar_abre_la_solicitud_su_ticket_y_manda_la_constancia(self):
        enlace = self.pedir_enlace()
        r = self.confirmar(enlace)
        s = SolicitudSupresion.objects.get()
        ticket = s.ticket
        self.assertRedirects(r, reverse('mi_ticket', args=[ticket.pk]), fetch_redirect_response=False)
        self.assertEqual((s.usuario, s.rol, s.estado), (self.beto.user, 'alumno', SolicitudSupresion.ABIERTA))
        self.assertEqual((ticket.categoria, ticket.autor, ticket.asignado), (Ticket.PRIVACIDAD, self.beto.user, self.agente))
        self.assertLess(ticket.vence - timezone.now(), timedelta(days=15))
        constancia = [m for m in mail.outbox if f'solicitud #{s.pk}' in m.subject][0]
        self.assertEqual(constancia.to, [self.beto.user.email])
        self.assertIn(f'#{s.pk}', constancia.body)
        self.assertIn(f'{timezone.localtime(ticket.vence):%d-%m-%Y}', constancia.body)

    def test_sin_marcar_confirmo_no_se_abre(self):
        r = self.client.post(self.pedir_enlace(), {})
        self.assertContains(r, 'Marca la casilla')
        self.assertFalse(SolicitudSupresion.objects.exists())

    def test_el_enlace_de_otra_cuenta_no_sirve(self):
        enlace = self.pedir_enlace()
        self.entrar(RUT_ANA)
        r = self.client.post(enlace, {'confirmo': 'on'}, follow=True)
        self.assertContains(r, 'es de otra cuenta')
        self.assertFalse(SolicitudSupresion.objects.exists())

    def test_un_enlace_falso_no_sirve(self):
        r = self.client.get(reverse('confirmar_eliminar_cuenta', args=['falso']), follow=True)
        self.assertContains(r, 'no es válido')

    def test_el_enlace_vence_a_las_24_horas(self):
        token = signing.dumps({'usuario': self.beto.user_id}, salt=identidad.SAL)
        identidad.verificar(token, self.beto.user)
        with mock.patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 25 * 3600):
            with self.assertRaises(ValidationError):
                identidad.verificar(token, self.beto.user)

    def test_confirmar_dos_veces_no_duplica(self):
        enlace = self.pedir_enlace()
        self.confirmar(enlace)
        r = self.confirmar(enlace, confirmo='on', _otra='1')
        self.assertEqual(SolicitudSupresion.objects.count(), 1)
        self.assertEqual(Ticket.objects.filter(categoria=Ticket.PRIVACIDAD).count(), 1)
        self.assertEqual(r.status_code, 302)

    def test_con_una_solicitud_abierta_la_pagina_muestra_su_estado(self):
        self.confirmar(self.pedir_enlace())
        r = self.client.get(reverse('eliminar_cuenta'))
        self.assertContains(r, 'Ya pediste eliminar tu cuenta')
        self.assertNotContains(r, 'Enviarme el enlace')

    def test_la_cuenta_sigue_activa_mientras_se_revisa(self):
        self.confirmar(self.pedir_enlace())
        self.assertTrue(User.objects.get(pk=self.beto.user_id).is_active)
        self.assertEqual(self.client.get(reverse('mis_tickets')).status_code, 200)

    def test_si_el_ticket_se_cerro_por_la_via_normal_puede_pedirlo_de_nuevo(self):
        self.confirmar(self.pedir_enlace())
        primera = SolicitudSupresion.objects.get()
        agregar_mensaje(primera.ticket, self.agente.user, 'Te respondo por aquí', de_soporte=True, cerrar=True)
        nueva, creada = solicitud.abrir(self.beto.user)
        self.assertTrue(creada)
        primera.refresh_from_db()
        self.assertEqual(primera.estado, SolicitudSupresion.RECHAZADA)
        self.assertEqual(SolicitudSupresion.objects.filter(estado=SolicitudSupresion.ABIERTA).get(), nueva)

    def test_el_enlace_de_mis_tickets_lleva_a_la_pagina(self):
        self.assertContains(self.client.get(reverse('mis_tickets')), reverse('eliminar_cuenta'))

    def test_anonimo_va_al_login(self):
        self.client.logout()
        r = self.client.get(reverse('eliminar_cuenta'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r.url)

    def test_un_alumno_menor_no_puede(self):
        user = User.objects.create_user('9999999-9', rut='9999999-9', email='menor@demo.cl', first_name='Mini',
                                        fecha_nacimiento=hace_anios(12))
        alumno = Alumno.objects.create(user=user, nivel_educacion='media')
        entrar(self.client, user, alumno_id=alumno.id_alumno)
        r = self.client.get(reverse('eliminar_cuenta'))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('eliminar-cuenta', r.url)

    def test_el_profesor_ve_que_se_elimina_y_que_se_conserva_y_puede_pedirlo(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('eliminar_cuenta'))
        self.assertContains(r, 'Título profesional')
        self.assertContains(r, 'Cuenta bancaria y horario')
        self.assertNotContains(r, 'no se elimina desde aquí')
        enlace = self.pedir_enlace()
        self.confirmar(enlace)
        self.assertEqual(SolicitudSupresion.objects.get().rol, 'profesor')


class SinDatosPersonalesTests(Escenario):
    """La solicitud es un registro que sobrevive a la cuenta: no puede guardar datos de la persona."""

    def test_el_modelo_no_tiene_campos_de_datos_personales(self):
        campos = {f.name for f in SolicitudSupresion._meta.get_fields()}
        self.assertFalse(campos & {'nombre', 'correo', 'email', 'rut', 'telefono', 'first_name'})
