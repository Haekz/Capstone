"""Aviso previo al chat (E5, respuesta legal 02-nov): finalidad, filtro, quien lee, conservacion y derechos, en las
tres bandejas, y una version simple para el estudiante menor. Datos ficticios."""

from unittest import mock

from django.urls import reverse

from apoderados.models import Apoderado
from mensajes import retencion, revision, servicio
from mensajes.models import Conversacion
from tests.test_apoderados import RUT, crear_apoderado, entrar
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_paquetes import RUT_ANA, RUT_PROFE, Escenario, dar_paquete

TITULO = 'Cómo funcionan los mensajes y qué pasa con tus datos'
ABIERTO = '<details class="aviso-mensajes" open'
CERRADO = '<details class="aviso-mensajes"'
MENOR = 'Cómo se hablan tu apoderado y tu profesor'


class AvisoDelAlumnoTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.entrar(RUT_ANA)

    def panel(self, **params):
        return self.client.get(reverse('alumno_pag1'), params)

    def test_antes_de_abrir_una_conversacion_va_desplegado(self):
        r = self.panel()
        self.assertContains(r, TITULO, count=1)
        self.assertContains(r, ABIERTO)

    def test_dentro_de_una_conversacion_va_plegado(self):
        conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        r = self.panel(c=conversacion.pk)
        self.assertContains(r, TITULO, count=1)
        self.assertContains(r, CERRADO)
        self.assertNotContains(r, ABIERTO)

    def test_explica_finalidad_filtro_lectura_conservacion_y_derechos(self):
        r = self.panel()
        for texto in ('solo para coordinar las clases', 'Filtro automático', 'Ninguna persona lee los mensajes por este filtro',
                      'solo puede leer una conversación si alguien la reporta', 'queda registrado quién la abrió',
                      'El administrador no puede leerlas', 'no incluye el mensaje',
                      'se conserva mientras soporte la revisa', 'Tus derechos'):
            self.assertContains(r, texto)

    def test_los_plazos_salen_de_las_constantes_reales(self):
        self.assertContains(self.panel(), f'pasan {retencion.DIAS_SIN_ACTIVIDAD} días sin mensajes')
        self.assertContains(self.panel(), f'revisión cada {revision.MESES_REVISION} meses')
        with mock.patch.object(retencion, 'DIAS_SIN_ACTIVIDAD', 45), mock.patch.object(revision, 'MESES_REVISION', 3):
            r = self.panel()
        self.assertContains(r, 'pasan 45 días sin mensajes')
        self.assertContains(r, 'revisión cada 3 meses')
        self.assertNotContains(r, 'pasan 90 días')

    def test_el_canal_de_derechos_apunta_a_lo_que_existe(self):
        r = self.panel()
        self.assertContains(r, f'href="{reverse("mis_tickets")}"')
        self.assertContains(r, f'href="{reverse("eliminar_cuenta")}"')

    def test_no_inventa_un_correo_de_contacto(self):
        self.assertNotContains(self.panel(), 'mailto:')

    def test_el_adulto_no_ve_la_version_del_menor(self):
        self.assertNotContains(self.panel(), MENOR)

    def test_la_frase_vieja_con_el_numero_escrito_a_mano_ya_no_esta(self):
        self.assertNotContains(self.panel(), 'Los mensajes se eliminan tras 90 días sin actividad')


class AvisoDelProfesorTests(Escenario):

    def test_el_profesor_lo_ve_antes_de_tener_conversaciones(self):
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'))
        self.assertContains(r, TITULO, count=1)
        self.assertContains(r, ABIERTO)
        self.assertContains(r, 'el alumno o su apoderado')

    def test_dentro_de_una_conversacion_va_plegado(self):
        dar_paquete(self.ana, self.profe)
        conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        self.entrar(RUT_PROFE)
        r = self.client.get(reverse('panel_profesor'), {'c': conversacion.pk})
        self.assertContains(r, TITULO, count=1)
        self.assertNotContains(r, ABIERTO)


class AvisoDelApoderadoTests(Escenario):

    def setUp(self):
        self.apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.vinculo = crear_menor_vinculado(self.apoderado, rut='77777777-7')
        dar_paquete(self.vinculo.alumno, self.profe)
        entrar(self.client, self.apoderado.user, apoderado_id=self.apoderado.id_apoderado)

    def test_el_apoderado_lo_ve_y_se_le_explica_que_el_profesor_no_ve_su_nombre(self):
        r = self.client.get(reverse('mensajes_apoderado'))
        self.assertContains(r, TITULO, count=1)
        self.assertContains(r, ABIERTO)
        self.assertContains(r, 'si eres madre, padre o tutor legal')
        self.assertContains(r, 'no tu nombre')

    def test_dentro_de_una_conversacion_va_plegado(self):
        self.client.post(reverse('mensajes_apoderado_abrir', args=[self.vinculo.pk, self.profe.pk]))
        conversacion = Conversacion.objects.get()
        r = self.client.get(reverse('mensajes_apoderado'), {'c': conversacion.pk})
        self.assertContains(r, TITULO, count=1)
        self.assertNotContains(r, ABIERTO)


class AvisoDelMenorTests(Escenario):

    def setUp(self):
        apoderado = crear_apoderado(RUT, Apoderado.VERIFICADO)
        self.menor = crear_menor_vinculado(apoderado, rut='77777777-7').alumno

    def test_el_menor_ve_la_version_simple_y_no_la_de_adultos(self):
        entrar(self.client, self.menor.user, alumno_id=self.menor.id_alumno)
        r = self.client.get(reverse('alumno_pag1'))
        self.assertContains(r, MENOR, count=1)
        self.assertContains(r, 'Tú no escribes mensajes aquí')
        self.assertContains(r, f'Si pasan {retencion.DIAS_SIN_ACTIVIDAD} días sin mensajes, se borran solos')
        self.assertNotContains(r, TITULO)
