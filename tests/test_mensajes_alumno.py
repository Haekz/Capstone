"""Buzon real del alumno adulto (paso C1b-2, decidido 02-nov). Datos ficticios."""

from django.urls import reverse

from apoderados.models import Apoderado
from mensajes import servicio
from mensajes.models import Conversacion, Mensaje
from notificaciones.models import Notificacion
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete

RUT_MENOR = '77777777-7'


class BuzonDelAlumnoTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)  # el Buzon es de quienes tienen un paquete vigente
        self.entrar(RUT_ANA)

    def panel(self, **params):
        return self.client.get(reverse('alumno_pag1'), params)

    def conversar(self, autor, texto):
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(autor, self.conversacion, texto)

    def abrir(self):
        self.client.post(reverse('mensajes_alumno_abrir', args=[self.profe.pk]))
        self.conversacion = Conversacion.objects.get()

    def test_ya_no_hay_profesores_ni_respuestas_inventadas(self):
        r = self.panel()
        for falso in ('activeChats', 'sendMessageToTeacher', 'Recuerda subir tu código al repositorio',
                      'Te acabo de adjuntar una guía'):  # frases de la maqueta del chat
            self.assertNotContains(r, falso)

    def test_ofrece_escribir_al_profesor_con_quien_tiene_paquete(self):
        r = self.panel()
        self.assertContains(r, reverse('mensajes_alumno_abrir', args=[self.profe.pk]))
        self.assertContains(r, 'Aún no han conversado')

    def test_abrir_crea_la_conversacion_y_lleva_al_buzon(self):
        r = self.client.post(reverse('mensajes_alumno_abrir', args=[self.profe.pk]))
        conversacion = Conversacion.objects.get()
        self.assertRedirects(r, f"{reverse('alumno_pag1')}?c={conversacion.pk}")
        self.assertEqual((conversacion.alumno, conversacion.profesor, conversacion.cliente),
                         (self.ana, self.profe, self.ana.user))

    def test_sin_relacion_con_ese_profesor_se_explica_y_no_se_crea(self):
        r = self.client.post(reverse('mensajes_alumno_abrir', args=[self.otro.pk]), follow=True)
        self.assertContains(r, 'Solo pueden escribirse quienes tienen una clase reservada o un paquete activo')
        self.assertFalse(Conversacion.objects.exists())
        self.assertNotContains(self.panel(), 'Solo pueden escribirse')  # el error se muestra una sola vez

    def test_la_lista_muestra_solo_el_nombre_de_pila_del_profesor(self):
        self.abrir()
        self.conversar(self.profe.user, 'Hola Ana, ¿cómo vas?')
        r = self.panel()
        self.assertContains(r, 'contact-name">Profe')
        self.assertContains(r, 'Hola Ana, ¿cómo vas?')
        for privado in filter(None, (RUT_PROFE, self.profe.user.email, self.profe.user.last_name)):
            self.assertNotContains(r, privado)

    def test_lo_nuevo_del_profesor_sale_sin_leer_hasta_abrirlo(self):
        self.abrir()
        self.conversar(self.profe.user, 'Hola Ana')
        self.assertContains(self.panel(), 'chat-contact-item unread')
        r = self.panel(c=self.conversacion.pk)
        self.assertContains(r, 'message-row received')
        self.assertNotContains(self.panel(), 'chat-contact-item unread')

    def test_enviar_guarda_avisa_al_profesor_con_enlace_y_vuelve(self):
        self.abrir()
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post(reverse('mensajes_alumno_enviar', args=[self.conversacion.pk]),
                                 {'texto': 'Profe, ¿vemos álgebra?'})
        self.assertRedirects(r, f"{reverse('alumno_pag1')}?c={self.conversacion.pk}")
        self.assertEqual(Mensaje.objects.get().autor, self.ana.user)
        aviso = Notificacion.objects.get(usuario=self.profe.user)
        self.assertEqual(aviso.enlace, f"{reverse('panel_profesor')}?c={self.conversacion.pk}")
        self.assertContains(self.panel(c=self.conversacion.pk), 'message-row sent')

    def test_el_aviso_al_alumno_lleva_a_su_buzon(self):
        self.abrir()
        self.conversar(self.profe.user, 'Hola Ana')
        self.assertEqual(Notificacion.objects.get(usuario=self.ana.user).enlace,
                         f"{reverse('alumno_pag1')}?c={self.conversacion.pk}")

    def test_un_contacto_se_bloquea_y_el_motivo_se_ve_una_sola_vez(self):
        self.abrir()
        r = self.client.post(reverse('mensajes_alumno_enviar', args=[self.conversacion.pk]),
                             {'texto': 'escribeme a ana@gmail.com'}, follow=True)
        self.assertContains(r, 'No puedes compartir un correo electrónico por aquí')
        self.assertFalse(Mensaje.objects.exists())
        self.assertNotContains(self.panel(c=self.conversacion.pk), 'No puedes compartir')

    def test_no_puede_escribir_en_la_conversacion_de_otro_alumno(self):
        dar_paquete(self.beto, self.profe)
        ajena = servicio.abrir_conversacion(self.beto, self.profe)
        r = self.client.post(reverse('mensajes_alumno_enviar', args=[ajena.pk]), {'texto': 'Hola'})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Mensaje.objects.exists())

    def test_la_conversacion_de_otro_no_se_abre_ni_se_marca(self):
        dar_paquete(self.beto, self.profe)
        ajena = servicio.abrir_conversacion(self.beto, self.profe)
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(self.profe.user, ajena, 'Mensaje privado para Beto')
        r = self.panel(c=ajena.pk)
        self.assertNotContains(r, 'Mensaje privado para Beto')
        ajena.refresh_from_db()
        self.assertIsNone(ajena.visto_cliente)

    def test_el_profesor_no_puede_usar_las_vistas_del_alumno(self):
        self.abrir()
        self.entrar(RUT_PROFE)
        self.client.post(reverse('mensajes_alumno_enviar', args=[self.conversacion.pk]), {'texto': 'Hola'})
        self.assertFalse(Mensaje.objects.exists())

    def test_enviar_solo_por_post(self):
        self.abrir()
        self.assertEqual(self.client.get(reverse('mensajes_alumno_enviar', args=[self.conversacion.pk])).status_code, 405)


class MenoresSinBuzonTests(Escenario):

    def setUp(self):
        self.vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        self.menor = self.vinculo.alumno
        dar_paquete(self.menor, self.profe)
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)

    def test_el_menor_no_ve_el_buzon_ni_a_quien_escribir(self):
        r = self.client.get(reverse('alumno_pag1'), {'c': 1})
        self.assertNotContains(r, 'inbox-layout')
        self.assertNotContains(r, reverse('mensajes_alumno_abrir', args=[self.profe.pk]))
        self.assertNotContains(r, "switchView('view-inbox');\n")  # ni se abre sola con ?c=

    def test_el_menor_no_puede_abrir_una_conversacion_ni_por_url(self):
        self.client.post(reverse('mensajes_alumno_abrir', args=[self.profe.pk]))
        self.assertFalse(Conversacion.objects.exists())
