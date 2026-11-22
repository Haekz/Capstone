"""Recordatorios de clase (21-nov): 24 y 2 horas antes, a alumno (o apoderados) y profesor. Datos ficticios.

`enviar_pendientes(ahora)` recibe la hora: asi se simula el paso del tiempo sin esperar. Las reservas se hacen sin
ejecutar los avisos de reserva (on_commit no corre en TestCase), asi que el buzon solo trae recordatorios.
"""

from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from alumnos import avisos_profesor, recordatorios
from alumnos.models import Asignatura, Clase, Inscripcion, SesionClase
from alumnos.recordatorios import enviar_pendientes
from alumnos.services import InscripcionService
from apoderados.forms import VERSION_DECLARACION_VINCULO
from apoderados.models import Apoderado, CompraApoderado, Vinculo
from lbwus import salud
from notificaciones.models import Notificacion
from tests.test_apoderados import RUT, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_especialidad import crear_profesor
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

ASUNTO_DIA = 'Recordatorio: tu clase empieza en menos de 24 horas - LBWUS'


def horas(n):
    return n / 24  # crear_sesion recibe dias


class RecordatoriosTests(Escenario):

    def setUp(self):
        for persona, apellido in ((self.ana, 'Soto'), (self.profe, 'Rojas')):
            persona.user.last_name = apellido
            persona.user.save()
        self.ana.user.email, self.ana.user.telefono = 'ana@lbwus.cl', '922222222'
        self.ana.user.save()
        dar_paquete(self.ana, self.profe)

    def reservar(self, en_horas):
        return InscripcionService.inscribir_alumno_en_sesion(
            self.ana, crear_sesion(self.clase, dias=horas(en_horas)).pk)

    def faltando(self, inscripcion, n_horas):
        """La hora en que a `inscripcion` le faltan n_horas para empezar."""
        return inscripcion.sesion.fecha_hora_inicio - timedelta(hours=n_horas)

    def correos_a(self, user):
        return [m for m in mail.outbox if m.to == [user.email]]

    def test_el_de_un_dia_sale_a_las_24_horas_a_los_dos_y_solo_una_vez(self):
        inscripcion = self.reservar(72)
        self.assertEqual(enviar_pendientes(timezone.now()), (0, 0, 0))  # faltan 3 dias: aun no
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 23)), (1, 0, 0))
        for persona in (self.ana, self.profe):
            [correo] = self.correos_a(persona.user)
            self.assertEqual(correo.subject, ASUNTO_DIA)
            self.assertIn('en menos de 24 horas', correo.body)
            self.assertIn('Algebra', correo.alternatives[0][0])
            [aviso] = Notificacion.objects.filter(usuario=persona.user)
            self.assertEqual(aviso.enlace, reverse('detalle_clase', args=[inscripcion.pk]))
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 22)), (0, 0, 0))  # no se repite
        self.assertEqual(len(mail.outbox), 2)

    def test_el_de_dos_horas_sale_despues_y_tambien_una_vez(self):
        inscripcion = self.reservar(72)
        enviar_pendientes(self.faltando(inscripcion, 23))
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1.5)), (0, 1, 0))
        self.assertEqual(len(mail.outbox), 4)
        self.assertIn('en menos de 2 horas', self.correos_a(self.ana.user)[1].body)
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1)), (0, 0, 0))
        self.assertEqual(len(mail.outbox), 4)

    def test_una_reserva_con_menos_de_24_horas_no_recibe_el_de_un_dia(self):
        inscripcion = self.reservar(5)
        self.assertIsNotNone(inscripcion.recordatorio_1d)  # se dio por hecho al reservar
        self.assertIsNone(inscripcion.recordatorio_2h)
        self.assertEqual(enviar_pendientes(timezone.now()), (0, 0, 0))  # llegaria minutos despues de la confirmacion
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1.5)), (0, 1, 0))
        self.assertEqual(len(mail.outbox), 2)

    def test_una_reserva_con_menos_de_2_horas_no_recibe_ninguno(self):
        inscripcion = self.reservar(1.5)
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1)), (0, 0, 0))
        self.assertEqual(mail.outbox, [])

    def test_si_el_cron_se_atrasa_dentro_de_las_2_horas_sale_solo_el_de_2_horas(self):
        inscripcion = self.reservar(72)
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1)), (0, 1, 0))
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 0.5)), (0, 0, 0))
        self.assertEqual(len(mail.outbox), 2)  # un solo aviso, nunca «en 24 horas» a una hora de la clase

    def test_reagendar_reinicia_los_recordatorios(self):
        inscripcion = self.reservar(72)
        enviar_pendientes(self.faltando(inscripcion, 23))
        nueva = crear_sesion(self.clase, dias=horas(96))
        InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, nueva.pk)
        inscripcion.refresh_from_db()
        self.assertEqual((inscripcion.recordatorio_1d, inscripcion.recordatorio_2h), (None, None))
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 23)), (1, 0, 0))  # ahora para la hora nueva
        self.assertEqual(len(mail.outbox), 4)

    def test_reagendar_a_una_hora_cercana_omite_el_de_un_dia(self):
        inscripcion = self.reservar(72)
        nueva = crear_sesion(self.clase, dias=horas(10))
        InscripcionService.reprogramar_inscripcion(self.ana, inscripcion.pk, nueva.pk)
        inscripcion.refresh_from_db()
        self.assertIsNotNone(inscripcion.recordatorio_1d)
        self.assertIsNone(inscripcion.recordatorio_2h)
        self.assertEqual(enviar_pendientes(timezone.now()), (0, 0, 0))
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 1.5)), (0, 1, 0))

    def test_no_avisa_una_clase_cancelada(self):
        inscripcion = self.reservar(72)
        InscripcionService.cancelar_inscripcion(self.ana, inscripcion.pk)
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 23)), (0, 0, 0))
        self.assertEqual(mail.outbox, [])

    def test_no_avisa_una_sesion_cancelada(self):
        inscripcion = self.reservar(72)
        SesionClase.objects.filter(pk=inscripcion.sesion_id).update(estado=SesionClase.ESTADO_CANCELADA)
        self.assertEqual(enviar_pendientes(self.faltando(inscripcion, 23)), (0, 0, 0))
        self.assertEqual(mail.outbox, [])

    def test_nadie_recibe_rut_correo_ni_telefono_del_otro(self):
        inscripcion = self.reservar(72)
        enviar_pendientes(self.faltando(inscripcion, 23))
        privados = {self.ana.user: self.profe.user, self.profe.user: self.ana.user}
        for destinatario, ajeno in privados.items():
            [correo] = self.correos_a(destinatario)
            for dato in (ajeno.rut, ajeno.email, ajeno.telefono):
                with self.subTest(destinatario=destinatario.first_name, dato=dato):
                    self.assertTrue(dato)  # existe: si estuviera vacio la prueba no probaria nada
                    self.assertNotIn(dato, correo.body)
                    self.assertNotIn(dato, correo.alternatives[0][0])

    def test_una_reserva_que_falla_no_frena_a_las_demas_y_se_reintenta_sin_duplicar_la_campanita(self):
        primera, segunda = self.reservar(72), self.reservar(73.5)
        ahora = self.faltando(segunda, 23.5)  # a las dos les faltan menos de 24 horas
        real = avisos_profesor.recordatorio

        def falla_la_primera(inscripcion, plazo):
            if inscripcion.pk == primera.pk:
                raise RuntimeError('base caida')
            return real(inscripcion, plazo)

        with mock.patch('alumnos.recordatorios.avisos_profesor.recordatorio', side_effect=falla_la_primera), \
                self.assertLogs('alumnos.recordatorios', 'ERROR'):
            self.assertEqual(enviar_pendientes(ahora), (1, 0, 1))
        primera.refresh_from_db()
        self.assertIsNone(primera.recordatorio_1d)  # sin marcar: la proxima corrida lo reintenta
        self.assertEqual(Notificacion.objects.filter(usuario=self.ana.user).count(), 1)  # la de la que fallo se deshizo
        self.assertEqual(enviar_pendientes(ahora), (1, 0, 0))
        self.assertEqual(Notificacion.objects.filter(usuario=self.ana.user).count(), 2)  # una por reserva, sin duplicar


class RecordatoriosDelMenorTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.profesor = crear_profesor('44444444-4', 'profe@demo.cl', None)
        cls.clase = Clase.objects.create(asignatura=Asignatura.objects.create(nombre='Álgebra'),
                                         modalidad='online', profesor=cls.profesor)
        cls.madre = crear_apoderado(RUT, Apoderado.VERIFICADO)
        cls.vinculo = crear_menor_vinculado(cls.madre)
        cls.menor = cls.vinculo.alumno
        cls.padre = crear_apoderado('55555555-5', Apoderado.VERIFICADO)
        Vinculo.objects.create(apoderado=cls.padre, alumno=cls.menor, parentesco='padre', estado=Vinculo.VERIFICADO,
                               version_declaracion=VERSION_DECLARACION_VINCULO, declaracion_aceptada=timezone.now())
        cls.paquete = dar_paquete(cls.menor, cls.profesor)
        CompraApoderado.objects.create(paquete=cls.paquete, apoderado=cls.madre, vinculo=cls.vinculo)

    def test_el_aviso_va_a_cada_apoderado_y_al_profesor_pero_no_al_menor(self):
        inscripcion = InscripcionService.inscribir_alumno_en_sesion(
            self.menor, crear_sesion(self.clase, dias=3).pk, vinculo=self.vinculo)
        self.assertEqual(enviar_pendientes(inscripcion.sesion.fecha_hora_inicio - timedelta(hours=23)), (1, 0, 0))
        destinos = sorted(destino for m in mail.outbox for destino in m.to)
        self.assertEqual(destinos, sorted([self.madre.user.email, self.padre.user.email, self.profesor.user.email]))
        self.assertNotIn(self.menor.user.email, destinos)
        self.assertFalse(Notificacion.objects.filter(usuario=self.menor.user).exists())
        correo = next(m for m in mail.outbox if m.to == [self.madre.user.email])
        self.assertIn(f'La clase de {self.menor.user.first_name} (Álgebra)', correo.body)  # «de Ana», como en la reserva


class ComandoYSaludTests(TestCase):

    def setUp(self):
        cache.delete(salud.CLAVE_ULTIMOS_RECORDATORIOS)
        salud.marcar_corrida()  # las tareas diarias, al dia: aqui solo importan los recordatorios

    def test_una_corrida_sin_fallos_deja_el_latido_y_cuenta_lo_enviado(self):
        self.assertTrue(salud.recordatorios_atrasados())  # nunca corrio
        salida = StringIO()
        call_command('enviar_recordatorios_clases', stdout=salida)
        self.assertIn('0 de 24 horas, 0 de 2 horas, 0 con error', salida.getvalue())
        self.assertFalse(salud.recordatorios_atrasados())

    def test_una_corrida_con_fallos_termina_con_error_y_no_deja_el_latido(self):
        with mock.patch.object(recordatorios, 'enviar_pendientes', return_value=(1, 0, 2)), \
                self.assertLogs('alumnos.management.commands.enviar_recordatorios_clases', 'ERROR'):
            with self.assertRaisesMessage(CommandError, '2 con error'):
                call_command('enviar_recordatorios_clases', stdout=StringIO())
        self.assertTrue(salud.recordatorios_atrasados())

    def test_el_latido_se_vence_a_la_hora(self):
        ahora = timezone.now()
        salud.marcar_recordatorios(ahora - timedelta(minutes=59))
        self.assertFalse(salud.recordatorios_atrasados(ahora))
        salud.marcar_recordatorios(ahora - timedelta(minutes=61))
        self.assertTrue(salud.recordatorios_atrasados(ahora))

    def test_salud_ignora_los_recordatorios_hasta_que_se_enciende_el_interruptor(self):
        self.assertEqual(self.client.get(reverse('salud')).status_code, 200)  # sin Cron de recordatorios y sin aviso

    @override_settings(SALUD_RECORDATORIOS=True)
    def test_con_el_interruptor_encendido_salud_vigila_los_recordatorios(self):
        respuesta = self.client.get(reverse('salud'))
        self.assertEqual((respuesta.status_code, respuesta.json()), (503, {'estado': 'atrasado'}))
        salud.marcar_recordatorios()
        self.assertEqual(self.client.get(reverse('salud')).status_code, 200)
        salud.marcar_recordatorios(timezone.now() - timedelta(hours=2))
        self.assertEqual(self.client.get(reverse('salud')).status_code, 503)
