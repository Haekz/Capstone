"""Borrado de conversaciones sin actividad (paso C1d, decidido 02-nov). Datos ficticios."""

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from alumnos.models import Inscripcion
from mensajes import retencion, servicio
from mensajes.models import Conversacion, Mensaje
from soporte.models import Ticket
from soporte.tickets import abrir_reporte, cerrar_tickets
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete


def hace(dias):
    return timezone.now() - timedelta(days=dias)


class BorradoPorInactividadTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)  # solo para poder abrir la conversacion
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        Mensaje.objects.create(conversacion=self.conversacion, autor=self.ana.user, texto='Hola profe')
        self.ana.paquetes.update(fecha_fin=hace(1))  # el paquete se vence: la relacion ya no protege
        self.envejecer(100)

    def envejecer(self, dias, conversacion=None):
        """Mueve al pasado la creacion de la conversacion y de sus mensajes."""
        conversacion = conversacion or self.conversacion
        Conversacion.objects.filter(pk=conversacion.pk).update(creada=hace(dias))
        Mensaje.objects.filter(conversacion=conversacion).update(creado=hace(dias))

    def borrar(self):
        return retencion.borrar_inactivas()

    def existe(self):
        return Conversacion.objects.filter(pk=self.conversacion.pk).exists()

    def clase_de_ana(self, dias, estado=Inscripcion.ESTADO_CONFIRMADA):
        return Inscripcion.objects.create(alumno=self.ana, clase=self.clase, estado=estado,
                                          sesion=crear_sesion(self.clase, dias=dias, cupo=1))

    def test_sin_actividad_por_mas_de_90_dias_se_borra_con_sus_mensajes(self):
        self.assertEqual(self.borrar(), 1)
        self.assertFalse(self.existe())
        self.assertFalse(Mensaje.objects.exists())

    def test_con_menos_de_90_dias_se_queda(self):
        self.envejecer(89)
        self.assertEqual(self.borrar(), 0)
        self.assertTrue(self.existe())

    def test_un_mensaje_reciente_la_mantiene_aunque_la_conversacion_sea_vieja(self):
        Mensaje.objects.create(conversacion=self.conversacion, autor=self.profe.user, texto='Hola de nuevo')
        self.assertEqual(self.borrar(), 0)

    def test_sin_mensajes_cuenta_desde_que_se_creo(self):
        Mensaje.objects.all().delete()
        self.assertEqual(self.borrar(), 1)

    def test_una_conversacion_nueva_sin_mensajes_se_queda(self):
        Mensaje.objects.all().delete()
        self.envejecer(10)
        self.assertEqual(self.borrar(), 0)

    def test_la_ultima_clase_cuenta_como_actividad(self):
        self.clase_de_ana(-30)
        self.assertEqual(self.borrar(), 0)

    def test_una_clase_vieja_no_la_mantiene(self):
        self.clase_de_ana(-100)
        self.assertEqual(self.borrar(), 1)

    def test_una_reserva_futura_la_mantiene(self):
        self.clase_de_ana(3)
        self.assertEqual(self.borrar(), 0)

    def test_una_reserva_futura_cancelada_no_la_mantiene(self):
        self.clase_de_ana(3, estado=Inscripcion.ESTADO_CANCELADA)
        self.assertEqual(self.borrar(), 1)

    def test_la_clase_con_otro_profesor_no_cuenta(self):
        Inscripcion.objects.create(alumno=self.ana, clase=self.clase_otro,
                                   sesion=crear_sesion(self.clase_otro, dias=-5, cupo=1))
        self.assertEqual(self.borrar(), 1)

    def test_un_paquete_vigente_la_mantiene(self):
        dar_paquete(self.ana, self.profe, dias=10)
        self.assertEqual(self.borrar(), 0)

    def test_un_paquete_vigente_con_otro_profesor_no_cuenta(self):
        dar_paquete(self.ana, self.otro, dias=10)
        self.assertEqual(self.borrar(), 1)

    def test_un_ticket_abierto_de_cualquiera_de_los_dos_la_mantiene_hasta_cerrarse(self):
        for autor in (self.ana.user, self.profe.user):
            ticket = abrir_reporte(autor, Ticket.OTRO, 'Una duda', 'Texto')
            self.assertEqual(self.borrar(), 0)
            cerrar_tickets(Ticket.objects.filter(pk=ticket.pk))
        self.assertEqual(self.borrar(), 1)

    def test_una_conversacion_reportada_no_se_borra_ni_con_el_ticket_cerrado(self):
        servicio.reportar(self.ana.user, self.conversacion, 'Me incomoda.')
        cerrar_tickets(Ticket.objects.all())
        self.assertEqual(self.borrar(), 0)
        self.assertTrue(self.existe())

    def test_solo_se_borran_las_que_corresponden(self):
        dar_paquete(self.beto, self.profe)
        otra = servicio.abrir_conversacion(self.beto, self.profe)  # reciente y con paquete
        self.assertEqual(self.borrar(), 1)
        self.assertTrue(Conversacion.objects.filter(pk=otra.pk).exists())


class ComandoTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)
        self.ana.paquetes.update(fecha_fin=hace(1))
        Conversacion.objects.update(creada=hace(100))

    def correr(self, *args):
        salida = StringIO()
        call_command('borrar_conversaciones_inactivas', *args, stdout=salida)
        return salida.getvalue()

    def test_borra_e_informa_solo_la_cantidad(self):
        self.assertEqual(self.correr().strip(), 'Conversaciones borradas: 1')
        self.assertFalse(Conversacion.objects.exists())

    def test_simular_cuenta_sin_borrar(self):
        self.assertEqual(self.correr('--simular').strip(), 'Conversaciones que se borrarian: 1')
        self.assertTrue(Conversacion.objects.exists())
