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
from alumnos.models import Asignatura, Clase, Inscripcion, PaqueteClases, Profesor, SesionClase, SolicitudClaseExtra
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


class ResponderTests(Escenario):
    """El profesor acepta o rechaza; si pasa el plazo o la reserva ya no se puede, queda vencida."""

    def setUp(self):
        self.paquete = dar_paquete(self.ana, self.profe)
        self.ahora = timezone.now()
        self.inicio = el_dia(3)
        self.solicitud = clase_extra.solicitar(self.ana, self.clase, self.inicio, ahora=self.ahora)
        self.profesor = self.profe.user

    def responder(self, funcion, usuario=None, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            return funcion(self.solicitud, usuario or self.profesor, **extra)

    def aceptar(self, usuario=None, **extra):
        return self.responder(clase_extra.aceptar, usuario, **extra)

    def rechazar(self, usuario=None, **extra):
        return self.responder(clase_extra.rechazar, usuario, **extra)

    def estado(self):
        self.solicitud.refresh_from_db()
        return self.solicitud.estado

    def avisos_al_alumno(self):
        """(campanita, correos) que recibio Ana."""
        correos = [m for m in mail.outbox if m.to == [self.ana.user.email]]
        return list(Notificacion.objects.filter(usuario=self.ana.user)), correos

    def sin_cambios(self):
        self.assertEqual(self.estado(), SolicitudClaseExtra.PENDIENTE)
        self.assertIsNone(self.solicitud.sesion)
        self.assertEqual(self.avisos_al_alumno(), ([], []))

    # --- aceptar
    def test_aceptar_crea_la_sesion_y_reserva_con_el_paquete(self):
        solicitud = self.aceptar(ahora=self.ahora)
        self.assertEqual(solicitud.estado, SolicitudClaseExtra.ACEPTADA)
        self.assertEqual(solicitud.fecha_resolucion, self.ahora)
        sesion = solicitud.sesion
        self.assertEqual((sesion.clase, sesion.fecha_hora_inicio, sesion.fecha_hora_fin, sesion.cupo_maximo),
                         (self.clase, self.inicio, self.inicio + timedelta(minutes=60), 1))
        reserva = Inscripcion.objects.get(sesion=sesion)
        self.assertEqual((reserva.alumno, reserva.paquete, reserva.estado),
                         (self.ana, self.paquete, Inscripcion.ESTADO_CONFIRMADA))
        self.assertTrue(reserva.puede_unirse)  # la sala virtual la abre como a cualquier clase
        self.assertEqual(self.paquete.clases_disponibles, self.paquete.clases - 1)

    def test_la_sesion_creada_no_se_ofrece_a_nadie_mas(self):
        sesion = self.aceptar().sesion
        self.assertFalse(SesionClase.objects.disponibles().filter(pk=sesion.pk).exists())

    def test_aceptar_le_avisa_al_alumno_sin_datos_del_profesor(self):
        self.aceptar()
        campanitas, correos = self.avisos_al_alumno()
        self.assertEqual((len(campanitas), len(correos)), (1, 1))
        local = timezone.localtime(self.inicio)
        for texto in ('aceptó', 'clase extra', 'Algebra', f'{local:%d/%m/%Y a las 10:00}', 'se descontó una clase'):
            self.assertIn(texto, campanitas[0].texto)
        self.assertNotIn(self.profe.nombre, campanitas[0].texto + correos[0].body)

    def test_solo_el_profesor_de_la_clase_responde(self):
        for intruso in (self.otro.user, self.ana.user):
            with self.assertRaisesMessage(ValidationError, 'Solo el profesor de esta clase'):
                self.aceptar(intruso)
            with self.assertRaisesMessage(ValidationError, 'Solo el profesor de esta clase'):
                self.rechazar(intruso)
        self.sin_cambios()

    def test_el_profesor_sin_titulo_validado_no_responde(self):
        Profesor.objects.filter(pk=self.profe.pk).update(titulo_estado=Profesor.TITULO_EN_REVISION)
        with self.assertRaisesMessage(ValidationError, 'Solo el profesor de esta clase'):
            self.aceptar()

    def test_una_solicitud_ya_resuelta_no_se_responde_otra_vez(self):
        self.aceptar()
        for responder in (self.aceptar, self.rechazar):
            with self.assertRaisesMessage(ValidationError, 'ya está aceptada'):
                responder()
        self.assertEqual(Inscripcion.objects.filter(alumno=self.ana).count(), 1)  # no se reserva dos veces

    # --- cuando ya no se puede cumplir: queda vencida (y eso SI se guarda)
    def test_fuera_de_plazo_queda_vencida(self):
        tarde = self.solicitud.vence_el + timedelta(minutes=1)
        with self.assertRaisesMessage(ValidationError, 'Ya pasó el plazo'):
            self.aceptar(ahora=tarde)
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)
        self.assertEqual(self.solicitud.fecha_resolucion, tarde)
        self.assertIsNone(self.solicitud.sesion)
        self.assertFalse(Inscripcion.objects.exists())
        self.assertEqual(self.paquete.clases_disponibles, self.paquete.clases)
        self.assertIn('venció', self.avisos_al_alumno()[0][0].texto)

    def test_un_minuto_antes_del_plazo_aun_se_acepta(self):
        self.assertEqual(self.aceptar(ahora=self.solicitud.vence_el - timedelta(minutes=1)).estado,
                         SolicitudClaseExtra.ACEPTADA)

    def test_en_el_instante_del_plazo_ya_esta_vencida(self):
        with self.assertRaisesMessage(ValidationError, 'Ya pasó el plazo'):
            self.aceptar(ahora=self.solicitud.vence_el)
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)

    def test_si_al_aceptar_el_paquete_ya_no_tiene_clases_queda_vencida(self):
        self.paquete.delete()
        with self.assertRaisesMessage(ValidationError, 'No tienes clases disponibles'):
            self.aceptar()
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)
        self.assertFalse(SesionClase.objects.filter(fecha_hora_inicio=self.inicio).exists())  # sin sesion huerfana
        campanita = self.avisos_al_alumno()[0][0]
        self.assertIn('venció', campanita.texto)

    def test_si_el_paquete_vencio_entre_el_pedido_y_la_respuesta_queda_vencida(self):
        PaqueteClases.objects.filter(pk=self.paquete.pk).update(fecha_fin=self.inicio - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            self.aceptar()
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)

    def test_si_el_profesor_ya_tomo_esa_hora_queda_vencida(self):
        otra = crear_sesion(self.clase, dias=3)
        otra.fecha_hora_inicio, otra.fecha_hora_fin = self.inicio, self.inicio + timedelta(hours=1)
        otra.save(skip_clean=True)
        Inscripcion.objects.create(alumno=self.beto, clase=self.clase, sesion=otra,
                                   estado=Inscripcion.ESTADO_CONFIRMADA)
        with self.assertRaisesMessage(ValidationError, 'ya tiene una clase a esa hora'):
            self.aceptar()
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)
        self.assertEqual(SesionClase.objects.filter(fecha_hora_inicio=self.inicio).count(), 1)  # solo la de Beto

    # --- rechazar
    def test_rechazar_guarda_el_motivo_y_avisa_sin_gastar_clase(self):
        solicitud = self.rechazar(motivo='  Ese día no puedo  ', ahora=self.ahora)
        self.assertEqual((solicitud.estado, solicitud.motivo_rechazo, solicitud.fecha_resolucion),
                         (SolicitudClaseExtra.RECHAZADA, 'Ese día no puedo', self.ahora))
        self.assertIsNone(solicitud.sesion)
        self.assertFalse(Inscripcion.objects.exists())
        self.assertEqual(self.paquete.clases_disponibles, self.paquete.clases)
        campanitas, correos = self.avisos_al_alumno()
        self.assertEqual((len(campanitas), len(correos)), (1, 1))
        self.assertIn('no pudo aceptar', campanitas[0].texto)
        self.assertIn('Ese día no puedo', correos[0].body)

    def test_rechazar_sin_motivo_tambien_vale(self):
        self.assertEqual(self.rechazar().motivo_rechazo, '')
        self.assertNotIn('mensaje', self.avisos_al_alumno()[0][0].texto)

    def test_el_motivo_se_corta_en_500(self):
        self.assertEqual(len(self.rechazar(motivo='x' * 900).motivo_rechazo), 500)

    def test_rechazar_fuera_de_plazo_la_deja_vencida(self):
        with self.assertRaisesMessage(ValidationError, 'Ya pasó el plazo'):
            self.rechazar(ahora=self.solicitud.vence_el + timedelta(minutes=1))
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)

    # --- vencer las que nadie respondio
    def test_vencer_cierra_solo_las_pendientes_que_ya_pasaron_su_plazo(self):
        viva = clase_extra.solicitar(self.ana, self.clase, el_dia(5), ahora=self.ahora)
        ya_resuelta = clase_extra.solicitar(self.ana, self.clase, el_dia(6), ahora=self.ahora)
        SolicitudClaseExtra.objects.filter(pk=ya_resuelta.pk).update(
            estado=SolicitudClaseExtra.RECHAZADA, vence_el=self.ahora - timedelta(days=1))
        SolicitudClaseExtra.objects.filter(pk=viva.pk).update(vence_el=self.ahora + timedelta(hours=1))
        SolicitudClaseExtra.objects.filter(pk=self.solicitud.pk).update(vence_el=self.ahora - timedelta(minutes=1))
        with self.captureOnCommitCallbacks(execute=True):
            cerradas = clase_extra.vencer_las_vencidas(ahora=self.ahora)
        self.assertEqual(cerradas, 1)
        self.assertEqual(self.estado(), SolicitudClaseExtra.VENCIDA)
        self.assertEqual(self.solicitud.fecha_resolucion, self.ahora)
        for pk, esperado in ((viva.pk, SolicitudClaseExtra.PENDIENTE), (ya_resuelta.pk, SolicitudClaseExtra.RECHAZADA)):
            self.assertEqual(SolicitudClaseExtra.objects.get(pk=pk).estado, esperado)
        campanitas, correos = self.avisos_al_alumno()
        self.assertEqual((len(campanitas), len(correos)), (1, 1))
        self.assertIn('Nadie respondió a tiempo', campanitas[0].texto + correos[0].body)

    def test_vencer_no_repite_el_aviso(self):
        SolicitudClaseExtra.objects.update(vence_el=self.ahora - timedelta(minutes=1))
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(clase_extra.vencer_las_vencidas(ahora=self.ahora), 1)
            self.assertEqual(clase_extra.vencer_las_vencidas(ahora=self.ahora), 0)
        self.assertEqual(len(self.avisos_al_alumno()[0]), 1)
