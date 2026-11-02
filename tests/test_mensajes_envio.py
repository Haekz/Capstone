"""Quien puede escribir, el envio y los avisos de mensajes (paso C1a, decidido 02-nov). Datos ficticios."""

from datetime import timedelta

from django.core import mail
from django.utils import timezone

from alumnos.models import PaqueteClases
from alumnos.services import InscripcionService
from apoderados.models import Apoderado
from mensajes import servicio
from mensajes.filtro import ContactoBloqueado
from mensajes.models import Conversacion, Mensaje
from mensajes.servicio import MensajeError
from notificaciones.models import Notificacion
from tests.test_apoderados import RUT, crear_apoderado
from tests.test_apoderados_vinculos import crear_menor_vinculado
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete

RUT_MENOR = '77777777-7'


class QuienPuedeEscribirTests(Escenario):

    def test_sin_reserva_ni_paquete_no_se_abre_conversacion(self):
        with self.assertRaisesMessage(MensajeError, 'reservada o un paquete activo'):
            servicio.abrir_conversacion(self.ana, self.profe)
        self.assertFalse(Conversacion.objects.exists())

    def test_con_paquete_vigente_si(self):
        dar_paquete(self.ana, self.profe)
        self.assertEqual(servicio.abrir_conversacion(self.ana, self.profe).cliente, self.ana.user)

    def test_con_reserva_activa_aunque_el_paquete_ya_no_este_vigente(self):
        dar_paquete(self.ana, self.profe)
        InscripcionService.inscribir_alumno_en_sesion(self.ana, crear_sesion(self.clase, dias=3, cupo=1).pk)
        PaqueteClases.objects.update(fecha_fin=timezone.now() - timedelta(days=1))
        self.assertTrue(servicio.abrir_conversacion(self.ana, self.profe).pk)

    def test_paquete_vencido_sin_reserva_no(self):
        dar_paquete(self.ana, self.profe, dias=-1)
        with self.assertRaises(MensajeError):
            servicio.abrir_conversacion(self.ana, self.profe)

    def test_el_paquete_con_otro_profesor_no_sirve(self):
        dar_paquete(self.ana, self.otro)
        with self.assertRaises(MensajeError):
            servicio.abrir_conversacion(self.ana, self.profe)

    def test_hay_una_sola_conversacion_por_par(self):
        dar_paquete(self.ana, self.profe)
        self.assertEqual(servicio.abrir_conversacion(self.ana, self.profe),
                         servicio.abrir_conversacion(self.ana, self.profe))
        self.assertEqual(Conversacion.objects.count(), 1)

    def test_un_menor_no_abre_conversacion_ni_con_paquete(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        dar_paquete(vinculo.alumno, self.profe)
        with self.assertRaisesMessage(MensajeError, 'Los menores no tienen mensajes'):
            servicio.abrir_conversacion(vinculo.alumno, self.profe)

    def test_un_menor_no_puede_escribir_en_una_conversacion(self):
        vinculo = crear_menor_vinculado(crear_apoderado(RUT, Apoderado.VERIFICADO), rut=RUT_MENOR)
        dar_paquete(vinculo.alumno, self.profe)
        conversacion = Conversacion.objects.create(alumno=vinculo.alumno, profesor=self.profe,
                                                   cliente=vinculo.alumno.user)
        with self.assertRaisesMessage(MensajeError, 'No puedes escribir'):
            servicio.enviar(vinculo.alumno.user, conversacion, 'Hola profe')
        self.assertFalse(Mensaje.objects.exists())


class EnviarTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)

    def enviar(self, autor, texto):
        with self.captureOnCommitCallbacks(execute=True):
            return servicio.enviar(autor, self.conversacion, texto)

    def test_guarda_el_mensaje_sin_espacios_sobrantes(self):
        mensaje = self.enviar(self.ana.user, '  Hola profe, ¿me ayuda con álgebra?  ')
        self.assertEqual((mensaje.autor, mensaje.texto), (self.ana.user, 'Hola profe, ¿me ayuda con álgebra?'))

    def test_vacio_o_demasiado_largo_no(self):
        for texto, aviso in [('   ', 'Escribe un mensaje'), (None, 'Escribe un mensaje'),
                             ('x' * 1001, 'hasta 1000 caracteres')]:
            with self.subTest(texto=texto), self.assertRaisesMessage(MensajeError, aviso):
                self.enviar(self.ana.user, texto)
        self.assertEqual(self.enviar(self.ana.user, 'x' * 1000).texto, 'x' * 1000)

    def test_solo_participan_el_alumno_y_el_profesor(self):
        for intruso in (self.beto.user, self.otro.user):
            with self.subTest(intruso=intruso.first_name), self.assertRaisesMessage(MensajeError, 'No puedes escribir'):
                self.enviar(intruso, 'Hola')

    def test_el_profesor_responde(self):
        self.assertEqual(self.enviar(self.profe.user, 'Hola Ana').autor, self.profe.user)

    def test_bloquea_datos_de_contacto_y_no_guarda(self):
        with self.assertRaises(ContactoBloqueado):
            self.enviar(self.ana.user, 'Escribeme al 987654321')
        self.assertFalse(Mensaje.objects.exists())
        self.assertFalse(Notificacion.objects.exists())

    def test_si_se_acaba_la_relacion_ya_no_puede_escribir(self):
        PaqueteClases.objects.update(fecha_fin=timezone.now() - timedelta(days=1))
        with self.assertRaisesMessage(MensajeError, 'reservada o un paquete activo'):
            self.enviar(self.ana.user, 'Hola')


class AvisosDeMensajeTests(Escenario):

    def setUp(self):
        dar_paquete(self.ana, self.profe)
        self.conversacion = servicio.abrir_conversacion(self.ana, self.profe)

    def enviar(self, autor, texto='Hola'):
        with self.captureOnCommitCallbacks(execute=True):
            servicio.enviar(autor, self.conversacion, texto)

    def avisos(self, user):
        return list(Notificacion.objects.filter(usuario=user).values_list('texto', flat=True))

    def test_el_primer_mensaje_avisa_al_profesor_por_campanita_y_correo(self):
        self.enviar(self.ana.user, 'Necesito ayuda con la tarea secreta')
        self.assertEqual(self.avisos(self.profe.user), ['Ana te escribió un mensaje.'])
        [correo] = mail.outbox
        self.assertEqual((correo.subject, correo.to), ('Tienes un mensaje nuevo - LBWUS', ['profe@lbwus.cl']))

    def test_el_correo_no_lleva_el_contenido(self):
        self.enviar(self.ana.user, 'Necesito ayuda con la tarea secreta')
        self.assertNotIn('secreta', mail.outbox[0].body)
        self.assertNotIn('secreta', ' '.join(self.avisos(self.profe.user)))

    def test_varios_seguidos_no_repiten_el_aviso(self):
        for _ in range(3):
            self.enviar(self.ana.user)
        self.assertEqual(len(self.avisos(self.profe.user)), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_al_cambiar_el_turno_avisa_al_otro(self):
        self.enviar(self.ana.user)
        self.enviar(self.profe.user, 'Claro, dime')
        self.assertEqual(len(self.avisos(self.ana.user)), 1)
        self.enviar(self.ana.user, 'Gracias')
        self.assertEqual(len(self.avisos(self.profe.user)), 2)

    def test_el_aviso_solo_lleva_el_nombre_de_pila(self):
        self.enviar(self.ana.user)
        self.enviar(self.profe.user)
        for texto in self.avisos(self.profe.user) + self.avisos(self.ana.user):
            self.assertNotIn(self.profe.user.last_name or 'sin-apellido', texto)
            self.assertNotIn(self.ana.user.email, texto)
