"""Reseñas verificadas de profesores.

Reglas:
- Solo califica el alumno con una clase completada (Inscripcion.completadas()).
- Una reseña por contratación: por paquete (1, 4 u 8 clases) o, si la clase no
  salió de un paquete, por inscripción. Lo garantiza la base de datos.
- El alumno puede actualizarla solo después de completar una clase nueva del
  mismo paquete.
- Reportar no oculta la reseña. Solo un admin la oculta o la restaura, y cada
  decisión queda registrada en ModeracionResena.
"""

from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from alumnos.models import Inscripcion, PaqueteClases

# Criterios objetivos para reportar y para ocultar.
MOTIVOS = [
    ('ofensivo', 'Contenido ofensivo'),
    ('amenazas', 'Amenazas'),
    ('datos_personales', 'Divulga información personal'),
    ('normas', 'Incumple las normas de la plataforma'),
]


class ResenaQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(estado=Resena.ESTADO_VISIBLE)

    def de_profesor(self, profesor):
        return self.filter(inscripcion__clase__profesor=profesor)

    def de_la_contratacion(self, inscripcion):
        """Reseña que ya cubre la contratación de esta inscripción (vacío si no hay)."""
        if inscripcion.paquete_id:
            return self.filter(paquete_id=inscripcion.paquete_id)
        return self.filter(inscripcion=inscripcion, paquete__isnull=True)


class Resena(models.Model):
    ESTADO_VISIBLE = 'visible'
    ESTADO_OCULTA = 'oculta'
    ESTADOS = [(ESTADO_VISIBLE, 'Visible'), (ESTADO_OCULTA, 'Oculta por moderación')]

    # Clase completada que habilitó la reseña: de ella salen el alumno y el profesor.
    inscripcion = models.ForeignKey(Inscripcion, on_delete=models.CASCADE, related_name='resenas')
    paquete = models.ForeignKey(PaqueteClases, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='resenas')
    puntaje = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.CharField(max_length=1000, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_VISIBLE)
    creada = models.DateTimeField(auto_now_add=True)
    # Solo la cambia el alumno (la moderación no): decide si puede volver a editar.
    actualizada = models.DateTimeField(default=timezone.now)

    objects = ResenaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Reseña'
        ordering = ['-actualizada']
        constraints = [
            models.UniqueConstraint(fields=['paquete'], condition=Q(paquete__isnull=False),
                                    name='resena_unica_por_paquete'),
            models.UniqueConstraint(fields=['inscripcion'], condition=Q(paquete__isnull=True),
                                    name='resena_unica_por_inscripcion'),
            models.CheckConstraint(condition=Q(puntaje__gte=1, puntaje__lte=5),
                                   name='resena_puntaje_entre_1_y_5'),
        ]

    def __str__(self):
        return f'Reseña #{self.pk} ({self.puntaje}/5)'

    @property
    def autor_publico(self):
        """Primer nombre y una inicial: nunca RUT, correo ni nombre completo."""
        user = self.inscripcion.alumno.user
        partes = f'{user.first_name} {user.last_name}'.split()
        if not partes:
            return 'Alumno verificado'
        return partes[0] + (f' {partes[1][0].upper()}.' if len(partes) > 1 else '')

    def puede_actualizarse(self):
        """Solo si completó una clase nueva del mismo paquete desde la última vez."""
        if not self.paquete_id:
            return False
        return (Inscripcion.objects.filter(paquete_id=self.paquete_id).completadas()
                .filter(sesion__fecha_hora_fin__gt=self.actualizada).exists())

    def aplicar_moderacion(self, moderacion, administrador):
        """Aplica la decisión del admin, la registra y cierra los reportes pendientes."""
        estado_final = {
            ModeracionResena.OCULTAR: self.ESTADO_OCULTA,
            ModeracionResena.RESTAURAR: self.ESTADO_VISIBLE,
        }.get(moderacion.accion, self.estado)
        with transaction.atomic():
            self.estado = estado_final
            self.save(update_fields=['estado'])
            moderacion.resena = self
            moderacion.administrador = administrador
            moderacion.save()
            self.reportes.filter(estado=ReporteResena.ESTADO_PENDIENTE).update(
                estado=ReporteResena.ESTADO_RESUELTO)


class ReporteResena(models.Model):
    # Mismos estados que alumnos.Reporte.
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_RESUELTO = 'resuelto'
    ESTADOS = [(ESTADO_PENDIENTE, 'Pendiente'), (ESTADO_RESUELTO, 'Resuelto')]
    LIMITE_DIARIO = 5  # contra denuncias abusivas

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name='reportes')
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='reportes_resenas')
    motivo = models.CharField(max_length=20, choices=MOTIVOS)
    detalle = models.CharField(max_length=500, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_PENDIENTE)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Reporte de reseña'
        ordering = ['-creado']
        constraints = [
            models.UniqueConstraint(fields=['resena', 'remitente'], name='reporte_unico_por_usuario'),
        ]

    @classmethod
    def supera_limite(cls, user):
        desde = timezone.now() - timedelta(days=1)
        return cls.objects.filter(remitente=user, creado__gte=desde).count() >= cls.LIMITE_DIARIO


class ModeracionResena(models.Model):
    """Registro de cada decisión de moderación (trazabilidad)."""
    OCULTAR = 'ocultar'
    RESTAURAR = 'restaurar'
    MANTENER = 'mantener'
    ACCIONES = [(OCULTAR, 'Ocultar'), (RESTAURAR, 'Restaurar'), (MANTENER, 'Mantener visible')]

    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name='moderaciones')
    # SET_NULL: si se borra la cuenta del admin, la decisión sigue registrada.
    administrador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, related_name='moderaciones_resenas')
    accion = models.CharField(max_length=10, choices=ACCIONES)
    criterio = models.CharField(max_length=20, choices=MOTIVOS, blank=True)
    observacion = models.CharField(max_length=300, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Moderación de reseña'
        ordering = ['-fecha']
