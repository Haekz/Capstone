"""Solicitud de clase extra: el alumno propone un dia y hora fuera del horario del profesor.

alumnos/models/clase_extra.py: el registro y su plazo. Las reglas para pedirla, aceptarla y rechazarla
viven en alumnos/clase_extra.py (pruebas mas abajo en este archivo, a medida que se agregan).
"""

from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from alumnos.models import Inscripcion, SolicitudClaseExtra
from tests.test_paquetes import Escenario


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
