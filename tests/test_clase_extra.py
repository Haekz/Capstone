"""Solicitud de clase extra: el alumno propone un dia y hora fuera del horario del profesor.

alumnos/models/clase_extra.py: el registro y su plazo. Las reglas para pedirla, aceptarla y rechazarla
viven en alumnos/clase_extra.py (pruebas mas abajo en este archivo, a medida que se agregan).
"""

from datetime import datetime, time, timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from agenda.models import HorarioSemanal
from alumnos import clase_extra
from alumnos.exceptions import SinClasesDisponiblesError
from alumnos.models import Asignatura, Clase, Inscripcion, SolicitudClaseExtra
from notificaciones.models import Notificacion
from tests.test_apoderados_vincular import crear_alumno as crear_alumno_con_edad
from tests.test_filtros_clases import crear_sesion
from tests.test_paquetes import Escenario, dar_paquete


def el_dia(dias, hora=10):
    """Hora en punto local, `dias` dias despues de hoy: fija, no depende de cuando corre la prueba."""
    return timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=dias), time(hora)))


def crear(escenario, estado=SolicitudClaseExtra.PENDIENTE, horas=48, creada=None, **extra):
    """Solicitud de Ana a `horas` horas desde ahora, con su plazo calculado como lo hara el servicio."""
    inicio = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=horas)
    datos = dict(alumno=escenario.ana, clase=escenario.clase, fecha_hora_inicio=inicio, estado=estado,
                 vence_el=SolicitudClaseExtra.plazo(creada or timezone.now(), inicio))
    return SolicitudClaseExtra.objects.create(**{**datos, **extra})


class PlazoTests(Escenario):

    def test_responde_en_24_horas_si_la_clase_queda_lejos(self):
        creada = timezone.now()
        self.assertEqual(SolicitudClaseExtra.plazo(creada, creada + timedelta(days=5)), creada + timedelta(hours=24))

    def test_vence_4_horas_antes_si_la_clase_queda_mas_cerca_que_eso(self):
        creada = timezone.now()
        inicio = creada + timedelta(hours=10)
        self.assertEqual(SolicitudClaseExtra.plazo(creada, inicio), inicio - timedelta(hours=4))

    def test_en_el_empate_da_lo_mismo(self):
        creada = timezone.now()
        self.assertEqual(SolicitudClaseExtra.plazo(creada, creada + timedelta(hours=28)), creada + timedelta(hours=24))

    def test_la_anticipacion_es_la_misma_de_cancelar_sin_costo(self):
        self.assertEqual(SolicitudClaseExtra.ANTICIPACION_MINIMA, Inscripcion.ANTICIPACION_SIN_COSTO)


class ModeloTests(Escenario):

    def test_nace_pendiente_y_dura_60_minutos(self):
        solicitud = crear(self)
        self.assertEqual(solicitud.estado, SolicitudClaseExtra.PENDIENTE)
        self.assertEqual(solicitud.fecha_hora_fin - solicitud.fecha_hora_inicio, timedelta(minutes=60))
        self.assertEqual(solicitud.profesor, self.profe)
        self.assertIsNone(solicitud.sesion)
        self.assertEqual(solicitud.motivo_rechazo, '')

    def test_no_puede_haber_dos_pendientes_iguales(self):
        primera = crear(self)
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear(self, fecha_hora_inicio=primera.fecha_hora_inicio)

    def test_si_la_anterior_ya_se_resolvio_puede_pedirla_de_nuevo(self):
        primera = crear(self, estado=SolicitudClaseExtra.RECHAZADA)
        crear(self, fecha_hora_inicio=primera.fecha_hora_inicio)  # no falla

    def test_otra_hora_u_otro_alumno_no_chocan(self):
        primera = crear(self)
        crear(self, fecha_hora_inicio=primera.fecha_hora_inicio + timedelta(hours=1))
        crear(self, alumno=self.beto, fecha_hora_inicio=primera.fecha_hora_inicio)
        self.assertEqual(SolicitudClaseExtra.objects.count(), 3)


class SolicitarTests(Escenario):
    """Pedir la clase: lo que se exige y el aviso al profesor. Ana tiene un paquete vigente con `profe`."""

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)
        self.inicio = el_dia(3)

    def pedir(self, **extra):
        datos = dict(alumno=self.ana, clase=self.clase, inicio=self.inicio)
        return clase_extra.solicitar(**{**datos, **extra})

    def rechaza(self, mensaje, **extra):
        """Pedir falla con ese mensaje y no deja nada: ni solicitud ni aviso."""
        with self.assertRaisesMessage(ValidationError, mensaje), self.captureOnCommitCallbacks(execute=True):
            self.pedir(**extra)
        self.assertFalse(SolicitudClaseExtra.objects.exists())
        self.assertEqual((len(mail.outbox), Notificacion.objects.count()), (0, 0))

    # --- el caso feliz
    def test_crea_la_solicitud_pendiente_con_su_plazo(self):
        ahora = timezone.now()
        solicitud = self.pedir(ahora=ahora)
        self.assertEqual(solicitud.estado, SolicitudClaseExtra.PENDIENTE)
        self.assertEqual((solicitud.alumno, solicitud.clase, solicitud.fecha_hora_inicio),
                         (self.ana, self.clase, self.inicio))
        self.assertEqual(solicitud.vence_el, SolicitudClaseExtra.plazo(ahora, self.inicio))
        self.assertIsNone(solicitud.sesion)

    def test_el_mensaje_se_limpia_y_se_corta_en_500(self):
        self.assertEqual(self.pedir(mensaje='  Tengo prueba el viernes  ').mensaje, 'Tengo prueba el viernes')
        self.assertEqual(len(self.pedir(mensaje='x' * 900, inicio=el_dia(4)).mensaje), 500)
        self.assertEqual(self.pedir(inicio=el_dia(5)).mensaje, '')

    def test_avisa_al_profesor_por_correo_y_en_la_plataforma(self):
        with self.captureOnCommitCallbacks(execute=True):
            solicitud = self.pedir()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.profe.user.email])
        aviso = Notificacion.objects.get(usuario=self.profe.user)
        self.assertEqual(Notificacion.objects.count(), 1)
        local = timezone.localtime(solicitud.fecha_hora_inicio)
        for texto in ('Ana', 'clase extra', 'Algebra', f'{local:%d/%m/%Y a las 10:00}', 'Responde antes del'):
            self.assertIn(texto, aviso.texto)

    def test_dos_alumnos_pueden_pedir_la_misma_hora_y_el_profesor_elige(self):
        dar_paquete(self.beto, self.profe)
        self.pedir()
        self.pedir(alumno=self.beto)
        self.assertEqual(SolicitudClaseExtra.objects.count(), 2)

    # --- quien puede pedir
    def test_un_menor_no_la_pide_por_su_cuenta(self):
        menor = crear_alumno_con_edad('30000000-1', 12)
        self.rechaza('menores de edad las hace su apoderado', alumno=menor)

    def test_exige_un_paquete_con_ese_profesor(self):
        self.paquete.delete()
        with self.assertRaises(SinClasesDisponiblesError):
            self.pedir()
        self.assertFalse(SolicitudClaseExtra.objects.exists())

    def test_el_paquete_de_otro_profesor_no_sirve(self):
        self.paquete.delete()
        dar_paquete(self.ana, self.otro)
        with self.assertRaises(SinClasesDisponiblesError):
            self.pedir()

    def test_el_paquete_tiene_que_estar_vigente_el_dia_de_la_clase(self):
        self.paquete.delete()
        dar_paquete(self.ana, self.profe, dias=2)  # vence antes de la clase propuesta
        with self.assertRaises(SinClasesDisponiblesError):
            self.pedir()

    def test_el_profesor_tiene_que_poder_dictar(self):
        sin_titulo_clase = Clase.objects.create(asignatura=Asignatura.objects.get(nombre='Algebra'),
                                                modalidad='online', profesor=self.sin_titulo)
        dar_paquete(self.ana, self.sin_titulo)
        self.rechaza('aún no tiene su título validado', clase=sin_titulo_clase)

    # --- cuando
    def test_la_hora_tiene_que_ser_en_punto(self):
        self.rechaza('hora en punto', inicio=self.inicio.replace(minute=30))

    def test_pide_con_4_horas_de_anticipacion_como_minimo(self):
        ahora = timezone.now().replace(minute=0, second=0, microsecond=0)
        self.rechaza('al menos 4 horas de anticipación', inicio=ahora + timedelta(hours=3), ahora=ahora)
        self.assertTrue(self.pedir(inicio=ahora + timedelta(hours=4), ahora=ahora).pk)  # justo 4 h: sirve

    def test_no_se_pide_una_hora_pasada(self):
        self.rechaza('al menos 4 horas de anticipación', inicio=el_dia(-1))

    # --- fuera de su horario
    def test_no_vale_una_hora_dentro_de_una_franja_del_profesor(self):
        # Aunque aun no tenga bloques creados (por ejemplo, mas alla de las 4 semanas).
        HorarioSemanal.objects.create(profesor=self.profe, dia_semana=self.inicio.weekday(),
                                      hora_inicio=time(9), hora_fin=time(12))
        self.rechaza('parte de los horarios del profesor')

    def test_una_franja_de_otro_dia_u_otra_hora_no_estorba(self):
        HorarioSemanal.objects.create(profesor=self.profe, dia_semana=(self.inicio.weekday() + 1) % 7,
                                      hora_inicio=time(9), hora_fin=time(12))
        HorarioSemanal.objects.create(profesor=self.profe, dia_semana=self.inicio.weekday(),
                                      hora_inicio=time(11), hora_fin=time(13))
        self.assertTrue(self.pedir().pk)  # las 10:00 no estan en ninguna franja

    def test_no_vale_una_hora_que_ya_tiene_un_bloque_libre(self):
        sesion = crear_sesion(self.clase, dias=3)
        sesion.fecha_hora_inicio, sesion.fecha_hora_fin = self.inicio, self.inicio + timedelta(hours=1)
        sesion.save(skip_clean=True)
        self.rechaza('parte de los horarios del profesor')

    def test_si_el_profesor_ya_tiene_clase_a_esa_hora_lo_dice(self):
        sesion = crear_sesion(self.clase, dias=3)
        sesion.fecha_hora_inicio, sesion.fecha_hora_fin = self.inicio, self.inicio + timedelta(hours=1)
        sesion.save(skip_clean=True)
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=sesion,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        self.rechaza('ya tiene una clase a esa hora')

    # --- repetida
    def test_no_se_pide_dos_veces_lo_mismo_mientras_espera(self):
        self.pedir()
        with self.assertRaisesMessage(ValidationError, 'Ya pediste esa clase extra'):
            self.pedir()
        self.assertEqual(SolicitudClaseExtra.objects.count(), 1)

    def test_si_la_anterior_se_rechazo_puede_volver_a_pedirla(self):
        self.pedir()
        SolicitudClaseExtra.objects.update(estado=SolicitudClaseExtra.RECHAZADA)
        self.assertTrue(self.pedir().pk)
