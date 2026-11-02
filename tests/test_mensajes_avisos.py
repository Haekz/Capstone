"""Cuando se avisa de un mensaje nuevo: cambio de turno, o mas de 12 h desde el ultimo aviso a esa persona.
Datos ficticios."""

from datetime import timedelta

from django.utils import timezone

from mensajes import servicio
from mensajes.models import Conversacion
from notificaciones.models import Notificacion
from tests.test_paquetes import Escenario, dar_paquete


def hace(horas):
    return timezone.now() - timedelta(hours=horas)


class ReavisoTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)

    def escribir(self, autor, texto='Hola'):
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(autor, self.conversacion, texto)  # el mismo objeto de siempre: no debe importar

    def avisos(self, user):
        return Notificacion.objects.filter(usuario=user).count()

    def sello(self):
        self.conversacion.refresh_from_db()
        return self.conversacion

    def test_el_primer_mensaje_avisa_y_deja_el_sello_solo_de_quien_lo_recibe(self):
        self.escribir(self.ana.user)
        self.assertEqual(self.avisos(self.profe.user), 1)
        self.assertIsNotNone(self.sello().avisado_profesor)
        self.assertIsNone(self.sello().avisado_cliente)

    def test_varios_seguidos_dentro_de_12_horas_no_repiten_el_aviso(self):
        for _ in range(3):
            self.escribir(self.ana.user)
        self.assertEqual(self.avisos(self.profe.user), 1)

    def test_pasadas_12_horas_desde_el_ultimo_aviso_se_avisa_otra_vez_aunque_el_mensaje_anterior_sea_reciente(self):
        self.escribir(self.ana.user, 'Primero')
        self.escribir(self.ana.user, 'Segundo, hace un momento')  # el mensaje anterior es de hace segundos
        Conversacion.objects.filter(pk=self.conversacion.pk).update(avisado_profesor=hace(13))
        self.escribir(self.ana.user, 'No llego a la clase de hoy')
        self.assertEqual(self.avisos(self.profe.user), 2)

    def test_antes_de_12_horas_desde_el_ultimo_aviso_no(self):
        self.escribir(self.ana.user)
        Conversacion.objects.filter(pk=self.conversacion.pk).update(avisado_profesor=hace(11))
        self.escribir(self.ana.user)
        self.assertEqual(self.avisos(self.profe.user), 1)

    def test_el_re_aviso_renueva_el_sello(self):
        self.escribir(self.ana.user)
        Conversacion.objects.filter(pk=self.conversacion.pk).update(avisado_profesor=hace(13))
        self.escribir(self.ana.user)
        self.assertGreater(self.sello().avisado_profesor, hace(1))
        self.escribir(self.ana.user)  # recien avisado: no otra vez
        self.assertEqual(self.avisos(self.profe.user), 2)

    def test_el_cambio_de_turno_siempre_avisa(self):
        self.escribir(self.ana.user)
        self.escribir(self.profe.user, 'Claro, dime')
        self.assertEqual(self.avisos(self.ana.user), 1)
        self.assertIsNotNone(self.sello().avisado_cliente)
        self.escribir(self.ana.user, 'Gracias')
        self.assertEqual(self.avisos(self.profe.user), 2)  # volvio a cambiar el turno, sin esperar 12 h
