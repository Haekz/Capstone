"""Clases, sesiones con fecha y cupo, e inscripciones de alumnos."""

from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

from .usuarios import Alumno, Profesor


class Asignatura(models.Model):
    nombre = models.CharField(max_length=60, unique=True)

    def __str__(self):
        return self.nombre


class ClaseQuerySet(models.QuerySet):
    """Filtros del catalogo de clases que ve el alumno."""

    def habilitadas(self):
        """Clases de profesores con titulo aprobado (los unicos que pueden hacer clases)."""
        return self.filter(profesor__titulo_estado=Profesor.TITULO_APROBADO)

    def con_disponibilidad(self):
        """Clases con al menos una sesion programada, futura y con cupo (ver SesionClaseQuerySet.disponibles)."""
        sesiones = SesionClase.objects.disponibles().filter(clase=models.OuterRef('pk'))
        return self.filter(models.Exists(sesiones))

    def filtrar(self, especialidad=None, modalidad=None, solo_disponibles=False):
        """Combina los filtros; los que vienen vacios no se aplican."""
        clases = self
        if especialidad:
            clases = clases.filter(profesor__especialidad=especialidad)
        if modalidad:
            clases = clases.filter(modalidad=modalidad)
        if solo_disponibles:
            clases = clases.con_disponibilidad()
        return clases


class Clase(models.Model):
    MODALIDADES = [('online', 'Online'), ('presencial', 'Presencial')]

    id_clase = models.AutoField(primary_key=True)
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    modalidad = models.CharField(max_length=10, choices=MODALIDADES)
    horario = models.TimeField()
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    en_vivo = models.BooleanField(default=False)
    descripcion_vivo = models.TextField(blank=True, null=True)
    temas_vivo = models.CharField(max_length=255, blank=True, null=True)

    objects = ClaseQuerySet.as_manager()

    def __str__(self):
        return f"{self.asignatura.nombre} - {self.profesor.user.first_name}"


class SesionClaseQuerySet(models.QuerySet):
    """QuerySet optimizado para consultas de disponibilidad y agenda de sesiones."""

    def activas(self):
        return self.exclude(estado='cancelada')

    def futuras(self):
        return self.filter(fecha_hora_inicio__gt=timezone.now())

    def programadas(self):
        return self.filter(estado='programada')

    def disponibles(self):
        """Sesiones programadas a futuro que aún cuentan con cupos libres.

        Y con el profesor libre: si ya tiene otra clase reservada que se cruza, no
        se ofrece (no puede estar en dos clases a la vez; decidido 02-nov, paso B1a).
        """
        profesor_ocupado = Inscripcion.objects.que_se_cruzan(
            models.OuterRef('clase__profesor'), models.OuterRef('fecha_hora_inicio'), models.OuterRef('fecha_hora_fin'),
        ).exclude(sesion=models.OuterRef('pk'))
        return (
            self.filter(
                estado='programada',
                fecha_hora_inicio__gt=timezone.now()
            )
            .annotate(
                cupos_ocupados_count=models.Count(
                    'inscripciones',
                    filter=models.Q(inscripciones__estado__in=['confirmada', 'pendiente'])
                )
            )
            .filter(cupos_ocupados_count__lt=models.F('cupo_maximo'))
            .exclude(models.Exists(profesor_ocupado))
        )

    def por_profesor(self, profesor):
        return self.filter(clase__profesor=profesor)

    def por_asignatura(self, asignatura):
        return self.filter(clase__asignatura=asignatura)


class SesionClaseManager(models.Manager.from_queryset(SesionClaseQuerySet)):
    pass


class SesionClase(models.Model):
    """
    Representa una sesión individual o evento puntual derivado de la plantilla Clase.
    Gestiona fecha/hora, control estricto de cupos, precio individual y disponibilidad.
    """

    ESTADO_PROGRAMADA = 'programada'
    ESTADO_EN_CURSO = 'en_curso'
    ESTADO_FINALIZADA = 'finalizada'
    ESTADO_CANCELADA = 'cancelada'

    ESTADOS_CHOICES = [
        (ESTADO_PROGRAMADA, 'Programada'),
        (ESTADO_EN_CURSO, 'En curso'),
        (ESTADO_FINALIZADA, 'Finalizada'),
        (ESTADO_CANCELADA, 'Cancelada'),
    ]

    id_sesion = models.AutoField(primary_key=True)
    clase = models.ForeignKey(
        Clase,
        on_delete=models.CASCADE,
        related_name='sesiones',
        verbose_name='Clase base'
    )
    fecha_hora_inicio = models.DateTimeField(verbose_name='Fecha y hora de inicio')
    fecha_hora_fin = models.DateTimeField(verbose_name='Fecha y hora de fin')
    cupo_maximo = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cupo máximo'
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio de la sesión'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_CHOICES,
        default=ESTADO_PROGRAMADA,
        db_index=True,
        verbose_name='Estado de la sesión'
    )

    objects = SesionClaseManager()

    class Meta:
        verbose_name = 'Sesión de Clase'
        verbose_name_plural = 'Sesiones de Clases'
        ordering = ['fecha_hora_inicio']
        indexes = [
            models.Index(fields=['clase', 'fecha_hora_inicio']),
            models.Index(fields=['estado', 'fecha_hora_inicio']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(fecha_hora_fin__gt=models.F('fecha_hora_inicio')),
                name='sesion_fin_posterior_a_inicio'
            ),
            models.CheckConstraint(
                check=models.Q(cupo_maximo__gt=0),
                name='sesion_cupo_maximo_positivo'
            ),
            models.CheckConstraint(
                check=models.Q(precio__gte=0),
                name='sesion_precio_no_negativo'
            ),
        ]

    def __str__(self):
        inicio_str = self.inicio_local.strftime('%d/%m/%Y %H:%M') if self.fecha_hora_inicio else 'Sin fecha'
        return f"{self.clase.asignatura.nombre} ({inicio_str}) - {self.get_estado_display()}"

    # strftime no convierte zona: para mostrar horas fuera de templates usar estas.
    @property
    def inicio_local(self):
        return timezone.localtime(self.fecha_hora_inicio)

    @property
    def fin_local(self):
        return timezone.localtime(self.fecha_hora_fin)

    def clean(self):
        super().clean()

        # 1. Validar que las fechas sean estrictamente a futuro en el momento de creación
        if not self.pk and self.fecha_hora_inicio:
            if self.fecha_hora_inicio <= timezone.now():
                raise ValidationError({
                    'fecha_hora_inicio': 'La fecha y hora de inicio debe ser estrictamente en el futuro.'
                })

        # 2. Validar coherencia fin > inicio
        if self.fecha_hora_inicio and self.fecha_hora_fin:
            if self.fecha_hora_fin <= self.fecha_hora_inicio:
                raise ValidationError({
                    'fecha_hora_fin': 'La fecha y hora de fin debe ser posterior a la fecha y hora de inicio.'
                })

        # 3. Validar cupo mayor a cero
        if self.cupo_maximo is not None and self.cupo_maximo < 1:
            raise ValidationError({
                'cupo_maximo': 'El cupo máximo debe ser de al menos 1 persona.'
            })

        # 4. Validar precio no negativo
        if self.precio is not None and self.precio < Decimal('0.00'):
            raise ValidationError({
                'precio': 'El precio no puede ser negativo.'
            })

    def save(self, *args, **kwargs):
        skip_clean = kwargs.pop('skip_clean', False)
        if not skip_clean:
            self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duracion_minutos(self):
        if self.fecha_hora_inicio and self.fecha_hora_fin:
            return int((self.fecha_hora_fin - self.fecha_hora_inicio).total_seconds() // 60)
        return 0

    @property
    def cupos_ocupados(self):
        return self.inscripciones.filter(
            estado__in=['confirmada', 'pendiente']
        ).count()

    @property
    def cupos_disponibles(self):
        return max(0, self.cupo_maximo - self.cupos_ocupados)

    @property
    def esta_disponible(self):
        return (
            self.estado == self.ESTADO_PROGRAMADA
            and bool(self.fecha_hora_inicio and self.fecha_hora_inicio > timezone.now())
            and self.cupos_disponibles > 0
        )

    def reservar(self, alumno):
        """
        Reserva atómica delegando al servicio transaccional con bloqueo a nivel de fila (select_for_update)
        para garantizar consistencia en entornos concurrentes (PostgreSQL).
        """
        from ..services import InscripcionService
        return InscripcionService.inscribir_alumno_en_sesion(alumno, self.pk)


class InscripcionQuerySet(models.QuerySet):
    def que_se_cruzan(self, profesor, inicio, fin):
        """Reservas activas del profesor cuyo bloque se cruza con [inicio, fin). Acepta OuterRef."""
        return self.filter(clase__profesor=profesor, estado__in=Inscripcion.ESTADOS_ACTIVOS,
                           sesion__fecha_hora_inicio__lt=fin, sesion__fecha_hora_fin__gt=inicio)

    def proximas(self):
        """Activas cuya sesion aun no termina (o inscritas a la clase sin sesion puntual)."""
        return self.filter(
            models.Q(sesion__isnull=True) | models.Q(sesion__fecha_hora_fin__gt=timezone.now()),
            estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_PENDIENTE],
        )

    def completadas(self):
        """Confirmadas en sesiones que ya terminaron y no se cancelaron."""
        return self.filter(
            estado=Inscripcion.ESTADO_CONFIRMADA,
            sesion__fecha_hora_fin__lte=timezone.now(),
        ).exclude(sesion__estado=SesionClase.ESTADO_CANCELADA)

    def consumidas(self):
        """Las que gastan una clase del paquete (y le pagan al profesor).

        Si el profesor cancela la sesion, la clase vuelve al alumno. Si el alumno
        cancela con menos de 4 h, no vuelve (decidido 02-nov).
        """
        return self.filter(estado__in=[*Inscripcion.ESTADOS_ACTIVOS, Inscripcion.ESTADO_CANCELADA_TARDE]).exclude(
            sesion__estado=SesionClase.ESTADO_CANCELADA
        )

    def pagables(self):
        """Las que se le pagan al profesor, ya pasada la hora: dictadas o canceladas con menos de 4 h.

        No reemplaza a completadas(): quien cancelo tarde no asistio (no califica ni suma progreso).
        """
        return self.filter(
            estado__in=[Inscripcion.ESTADO_CONFIRMADA, Inscripcion.ESTADO_CANCELADA_TARDE],
            sesion__fecha_hora_fin__lte=timezone.now(),
        ).exclude(sesion__estado=SesionClase.ESTADO_CANCELADA)


class Inscripcion(models.Model):
    ESTADO_CONFIRMADA = 'confirmada'
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_CANCELADA = 'cancelada'
    # Con menos de 4 h: la clase se pierde y el profesor cobra (decidido 02-nov). No ocupa cupo.
    ESTADO_CANCELADA_TARDE = 'cancelada_tarde'
    ESTADOS_ACTIVOS = [ESTADO_CONFIRMADA, ESTADO_PENDIENTE]  # ocupan cupo y consumen una clase
    ANTICIPACION_SIN_COSTO = timedelta(hours=4)  # para cancelar o reagendar sin perder la clase

    ESTADOS_CHOICES = [
        (ESTADO_CONFIRMADA, 'Confirmada'),
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_CANCELADA, 'Cancelada'),
        (ESTADO_CANCELADA_TARDE, 'Cancelada con menos de 4 h'),
    ]

    id_inscripcion = models.AutoField(primary_key=True)
    fecha_inscripcion = models.DateField(auto_now_add=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)
    sesion = models.ForeignKey(
        SesionClase,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='inscripciones',
        verbose_name='Sesión puntual'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_CHOICES,
        default=ESTADO_CONFIRMADA,
        db_index=True,
        verbose_name='Estado de inscripción'
    )
    # De que paquete salio la clase. Sin paquete: inscripciones de antes de los paquetes.
    paquete = models.ForeignKey(
        'PaqueteClases',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inscripciones',
    )

    objects = InscripcionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'
        constraints = [
            models.UniqueConstraint(
                fields=['alumno', 'sesion'],
                condition=models.Q(sesion__isnull=False, estado__in=['confirmada', 'pendiente']),
                name='unique_inscripcion_alumno_sesion_activa'
            ),
            models.UniqueConstraint(
                fields=['alumno', 'clase'],
                condition=models.Q(sesion__isnull=True, estado__in=['confirmada', 'pendiente']),
                name='unique_inscripcion_alumno_clase_activa'
            ),
        ]

    def clean(self):
        super().clean()
        if self.sesion and not getattr(self, 'clase_id', None):
            self.clase = self.sesion.clase
        elif self.sesion and getattr(self, 'clase_id', None) and self.clase_id != self.sesion.clase_id:
            raise ValidationError({'sesion': 'La sesión seleccionada no pertenece a la clase especificada.'})

    def save(self, *args, **kwargs):
        if self.sesion and not getattr(self, 'clase_id', None):
            self.clase = self.sesion.clase
        super().save(*args, **kwargs)

    @property
    def puede_unirse(self):
        """Solo una inscripcion confirmada, de una sesion no cancelada, entra a la sala virtual.

        'pendiente' solo la asigna un admin a mano: aun no esta confirmada.
        """
        sesion_cancelada = self.sesion_id is not None and self.sesion.estado == SesionClase.ESTADO_CANCELADA
        return self.estado == self.ESTADO_CONFIRMADA and not sesion_cancelada

    @property
    def puede_cancelar(self):
        """Activa y antes de que empiece la sesion: nadie toma la clase y despues recupera el credito.

        Con menos de 4 h tambien se puede, pero la clase se pierde (a_tiempo_para_cambiar).
        """
        empezo = self.sesion_id is not None and self.sesion.fecha_hora_inicio <= timezone.now()
        return self.estado in self.ESTADOS_ACTIVOS and not empezo

    @property
    def a_tiempo_para_cambiar(self):
        """Faltan 4 h o mas: cancelar o reagendar no cuesta la clase."""
        return self.sesion_id is None or self.sesion.fecha_hora_inicio - timezone.now() >= self.ANTICIPACION_SIN_COSTO

    @property
    def puede_reprogramar(self):
        """Reagendar es directo, pero solo con 4 h o mas de anticipacion."""
        return self.sesion_id is not None and self.puede_cancelar and self.a_tiempo_para_cambiar

    def __str__(self):
        if self.sesion:
            return f'{self.alumno} inscrito en {self.clase} (Sesión #{self.sesion.pk})'
        return f'{self.alumno} inscrito en {self.clase}'
