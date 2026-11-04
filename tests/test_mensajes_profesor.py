"""Buzon real del profesor (paso C1b-1, decidido 02-nov). Datos ficticios."""

from django.urls import reverse

from alumnos.models import Inscripcion
from alumnos.services import InscripcionService
from apoderados.models import Apoderado
from mensajes import servicio
from mensajes.models import Conversacion, Mensaje
from notificaciones.models import Notificacion
from tests.test_agenda_cancelar import EN_13_HORAS
from tests.test_apoderados import RUT, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete

RUT_MENOR = '77777777-7'


class BuzonDelProfesorTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        self.entrar(RUT_PROFE)

    def panel(self, **params):
        return self.client.get(reverse('panel_profesor'), params)

    def escribir(self, autor, texto):
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(autor, self.conversacion, texto)

    def test_ya_no_hay_conversaciones_inventadas(self):
        r = self.panel()
        self.assertNotContains(r, 'studentChats')
        self.assertNotContains(r, 'duda con la Clase 3 de variables')  # frase de la maqueta del chat

    def test_sin_conversaciones_lo_explica(self):
        Conversacion.objects.all().delete()
        self.assertContains(self.panel(), 'Aún no tienes conversaciones')

    def test_la_lista_muestra_solo_el_nombre_de_pila_y_el_ultimo_mensaje(self):
        self.escribir(self.ana.user, 'Hola profe, tengo una duda')
        r = self.panel()
        self.assertContains(r, 'profe-chat-student-name">Ana')
        self.assertContains(r, 'Hola profe, tengo una duda')
        for privado in filter(None, (RUT_ANA, self.ana.user.email, self.ana.user.last_name)):
            self.assertNotContains(r, privado)

    def test_lo_que_escribio_el_alumno_aparece_sin_leer_hasta_abrirlo(self):
        self.escribir(self.ana.user, 'Hola profe')
        self.assertContains(self.panel(), 'profe-chat-item unread')
        r = self.panel(c=self.conversacion.pk)
        self.assertContains(r, 'profe-chat-bubble-row received')
        self.assertNotContains(r, 'profe-chat-item active unread')
        self.assertNotContains(self.panel(), 'profe-chat-item unread')

    def test_lo_que_escribio_el_profesor_se_ve_como_enviado_y_no_cuenta_como_sin_leer(self):
        self.escribir(self.profe.user, 'Claro, dime')
        r = self.panel()
        self.assertNotContains(r, 'profe-chat-item unread')
        self.assertContains(self.panel(c=self.conversacion.pk), 'profe-chat-bubble-row sent')

    def test_una_conversacion_ajena_no_se_abre_ni_se_marca(self):
        dar_paquete(self.beto, self.otro)
        ajena = servicio.abrir_conversacion(self.beto, self.otro)
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(self.beto.user, ajena, 'Mensaje privado de otro profesor')
        r = self.panel(c=ajena.pk)
        self.assertContains(r, 'Elige una conversación de la lista')
        self.assertNotContains(r, 'Mensaje privado de otro profesor')
        ajena.refresh_from_db()
        self.assertIsNone(ajena.visto_profesor)

    def test_enviar_guarda_avisa_al_alumno_y_vuelve_a_la_conversacion(self):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse('mensajes_profesor_enviar', args=[self.conversacion.pk]),
                                 {'texto': 'Hola Ana, ¿cómo vas?'})
        self.assertRedirects(r, f"{reverse('panel_profesor')}?c={self.conversacion.pk}")
        self.assertEqual(Mensaje.objects.get().autor, self.profe.user)
        self.assertEqual(list(Notificacion.objects.filter(usuario=self.ana.user)
                              .values_list('texto', flat=True)), [f'{self.profe.user.first_name} te escribió un mensaje.'])

    def test_enviar_un_telefono_no_se_guarda_y_se_explica(self):
        r = self.client.post(reverse('mensajes_profesor_enviar', args=[self.conversacion.pk]),
                             {'texto': 'llamame al 987654321'}, follow=True)
        self.assertContains(r, 'No puedes compartir un teléfono por aquí')
        self.assertFalse(Mensaje.objects.exists())

    def test_no_puede_escribir_en_la_conversacion_de_otro_profesor(self):
        dar_paquete(self.beto, self.otro)
        ajena = servicio.abrir_conversacion(self.beto, self.otro)
        r = self.client.post(reverse('mensajes_profesor_enviar', args=[ajena.pk]), {'texto': 'Hola'})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Mensaje.objects.exists())

    def test_un_alumno_no_puede_usar_las_vistas_del_profesor(self):
        self.entrar(RUT_ANA)
        self.client.post(reverse('mensajes_profesor_enviar', args=[self.conversacion.pk]), {'texto': 'Hola'})
        self.assertFalse(Mensaje.objects.exists())

    def test_enviar_solo_por_post(self):
        self.assertEqual(self.client.get(reverse('mensajes_profesor_enviar', args=[self.conversacion.pk])).status_code, 405)

    def test_el_aviso_de_mensaje_nuevo_lleva_directo_a_la_conversacion(self):
        self.escribir(self.ana.user, 'Hola profe')
        aviso = Notificacion.objects.get(usuario=self.profe.user)
        self.assertEqual(aviso.enlace, f"{reverse('panel_profesor')}?c={self.conversacion.pk}")


class EscribirDesdeLaAgendaTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.inscripcion = InscripcionService.inscribir_alumno_en_sesion(
            self.ana, crear_sesion(self.clase, dias=EN_13_HORAS, cupo=1).pk)
        self.entrar(RUT_PROFE)

    def abrir(self, inscripcion):
        return self.client.post(reverse('mensajes_profesor_abrir', args=[inscripcion.pk]))

    def test_el_boton_aparece_junto_a_la_reserva_de_un_adulto(self):
        self.assertContains(self.client.get(reverse('panel_profesor')), 'Escribir al alumno</button>', count=1)

    def test_abre_la_conversacion_y_lleva_al_buzon(self):
        r = self.abrir(self.inscripcion)
        conversacion = Conversacion.objects.get()
        self.assertRedirects(r, f"{reverse('panel_profesor')}?c={conversacion.pk}")
        self.assertEqual((conversacion.alumno, conversacion.profesor, conversacion.cliente),
                         (self.ana, self.profe, self.ana.user))

    def test_abrirla_dos_veces_no_duplica(self):
        self.abrir(self.inscripcion)
        self.abrir(self.inscripcion)
        self.assertEqual(Conversacion.objects.count(), 1)

    def test_no_puede_abrir_con_la_reserva_de_otro_profesor(self):
        otra = Inscripcion.objects.create(alumno=self.beto, clase=self.clase_otro,
                                          sesion=crear_sesion(self.clase_otro, dias=EN_13_HORAS, cupo=1))
        self.assertEqual(self.abrir(otra).status_code, 404)
        self.assertFalse(Conversacion.objects.exists())

    def test_con_un_menor_el_boton_es_para_su_apoderado_y_abre_la_conversacion_con_el(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        dar_paquete(vinculo.alumno, self.profe)
        InscripcionService.inscribir_alumno_en_sesion(
            vinculo.alumno, crear_sesion(self.clase, dias=EN_13_HORAS + 1, cupo=1).pk, vinculo=vinculo)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, 'Escribir al alumno</button>', count=1)  # el de Ana
        self.assertContains(r, 'Escribir al apoderado</button>', count=1)  # el del menor
        self.abrir(Inscripcion.objects.get(alumno=vinculo.alumno))
        self.assertEqual(Conversacion.objects.get(alumno=vinculo.alumno).cliente, vinculo.apoderado.user)
