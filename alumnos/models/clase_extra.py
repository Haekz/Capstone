"""Solicitud de clase extra: el alumno propone un dia y hora fuera del horario del profesor.

Los estados solo avanzan: pendiente -> aceptada | rechazada | vencida. Aceptar crea la sesion y reserva
al alumno (alumnos/clase_extra.py); aqui solo vive el registro y su plazo.
"""

from datetime import timedelta

from django.db import models

from .clases import Clase, Inscripcion, SesionClase
from .usuarios import Alumno


class SolicitudClaseExtra(models.Model):
    PENDIENTE, ACEPTADA, RECHAZADA, VENCIDA = 'pendiente', 'aceptada', 'rechazada', 'vencida'
    ESTADOS = [(PENDIENTE, 'Pendiente'), (ACEPTADA, 'Aceptada'), (RECHAZADA, 'Rechazada'), (VENCIDA, 'Vencida')]

    DURACION = timedelta(minutes=60)  # igual que los bloques de la agenda
    PLAZO_RESPUESTA = timedelta(hours=24)
    # Con menos que esto antes de la clase ya no se puede cambiar sin costo (Inscripcion): tampoco tiene sentido pedirla.
    ANTICIPACION_MINIMA = Inscripcion.ANTICIPACION_SIN_COSTO

    id_solicitud = models.AutoField(primary_key=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='solicitudes_clase_extra')
    # La materia elegida: de ahi sale el profesor.
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name='solicitudes_extra')
    fecha_hora_inicio = models.DateTimeField()
    mensaje = models.CharField(max_length=500, blank=True, default='')
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    vence_el = models.DateTimeField()
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    motivo_rechazo = models.CharField(max_length=500, blank=True, default='')
    # La sesion que se crea al aceptar. SET_NULL: si se borra, la solicitud queda como historial.
    sesion = models.OneToOneField(SesionClase, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['-creada']
        verbose_name = 'Solicitud de clase extra'
        verbose_name_plural = 'Solicitudes de clase extra'
        constraints = [
            models.UniqueConstraint(
                fields=['alumno', 'clase', 'fecha_hora_inicio'], condition=models.Q(estado='pendiente'),
                name='una_solicitud_extra_pendiente_por_hora',
            ),
        ]

    def __str__(self):
        return f'Clase extra #{self.id_solicitud}: {self.alumno} con {self.profesor} ({self.get_estado_display().lower()})'

    @staticmethod
    def plazo(creada, inicio):
        """Responde en 24 h; si la clase queda mas cerca que eso, hasta 4 h antes de ella."""
        return min(creada + SolicitudClaseExtra.PLAZO_RESPUESTA, inicio - SolicitudClaseExtra.ANTICIPACION_MINIMA)

    @property
    def fecha_hora_fin(self):
        return self.fecha_hora_inicio + self.DURACION

    @property
    def profesor(self):
        return self.clase.profesor
