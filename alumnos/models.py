from datetime import timedelta
from decimal import Decimal
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone

# Create your models here.

class Genero(models.Model):
    id_genero = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    def __str__(self):
        return self.descripcion

class CustomUser(AbstractUser):
    ROLES = (
        ('alumno', 'Alumno'),
        ('profesor', 'Profesor'),
        ('admin', 'Administrador'),
        ('tutor', 'Tutor'),
    )
    rol = models.CharField(max_length=15, choices=ROLES, default='alumno')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=100, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True, blank=True)
    foto_perfil = models.ImageField(upload_to='perfiles/', null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"

    @property
    def is_alumno(self):
        return self.rol == 'alumno'

    @property
    def is_profesor(self):
        return self.rol == 'profesor'
        
    @property
    def is_tutor(self):
        return self.rol == 'tutor'

    @property
    def is_administrador(self):
        return self.rol == 'admin' or self.is_staff or self.is_superuser


class Tutor(models.Model):
    id_tutor = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_tutor')

    def __str__(self):
        return f"Tutor: {self.user.first_name} {self.user.last_name}"


class Alumno(models.Model):
    id_alumno = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_alumno')
    nivel_educacion = models.CharField(max_length=10, choices=[('basica', 'Básica'), ('media', 'Media'), ('superior', 'Superior')])
    tutor = models.ForeignKey(Tutor, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Alumno: {self.user.first_name} {self.user.last_name}"

    def resumen_progreso(self):
        """Horas, clases y ramos de las clases que el alumno ya completo (vista Mi Progreso)."""
        completadas = list(
            Inscripcion.objects.filter(alumno=self).completadas().select_related('sesion', 'clase')
        )
        minutos = sum(i.sesion.duracion_minutos for i in completadas)
        return {
            'horas': round(minutos / 60, 1),
            'clases': len(completadas),
            'ramos': len({i.clase.asignatura_id for i in completadas}),
        }

    def plan_vigente(self):
        """Suscripcion activa que vence mas tarde, o None si no tiene plan."""
        return self.suscripciones.vigentes().order_by('-fecha_fin').first()


class Especialidad(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    
    def __str__(self):
        return self.nombre


class Banco(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    
    def __str__(self):
        return self.nombre


class ProfesorQuerySet(models.QuerySet):
    def aprobados(self):
        return self.filter(titulo_estado='aprobado')

    def habilitados(self):
        """Profesores que ya pueden hacer clases (titulo aprobado)."""
        return self.aprobados()


class Profesor(models.Model):
    # Estados del titulo profesional. Sin titulo aprobado no se hacen clases.
    TITULO_PENDIENTE = 'pendiente'      # aun no lo sube
    TITULO_EN_REVISION = 'en_revision'  # subido, falta que un admin lo revise
    TITULO_APROBADO = 'aprobado'
    TITULO_RECHAZADO = 'rechazado'
    ESTADOS_TITULO = [
        (TITULO_PENDIENTE, 'Pendiente'),
        (TITULO_EN_REVISION, 'En revisión'),
        (TITULO_APROBADO, 'Aprobado'),
        (TITULO_RECHAZADO, 'Rechazado'),
    ]

    id_profesor = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_profesor')
    especialidad = models.ForeignKey(Especialidad, on_delete=models.SET_NULL, null=True)
    telefono_publico = models.BooleanField(default=False, help_text='¿Mostrar teléfono a los alumnos?')

    # Documento privado: se sirve solo a admins (ver admin_portal.ver_titulo),
    # nunca por MEDIA_URL publico.
    titulo_archivo = models.FileField(upload_to='titulos/', blank=True)
    titulo_estado = models.CharField(max_length=12, choices=ESTADOS_TITULO, default=TITULO_PENDIENTE)
    titulo_observacion = models.CharField(max_length=200, blank=True)
    titulo_actualizado = models.DateTimeField(null=True, blank=True)

    objects = ProfesorQuerySet.as_manager()

    def __str__(self):
        return f"Profesor: {self.user.first_name} {self.user.last_name}"

    @property
    def nombre(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    @property
    def puede_hacer_clases(self):
        return self.titulo_estado == self.TITULO_APROBADO

    @property
    def puede_subir_titulo(self):
        return self.titulo_estado in (self.TITULO_PENDIENTE, self.TITULO_RECHAZADO)


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
        """Sesiones programadas a futuro que aún cuentan con cupos libres."""
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
        from .services import InscripcionService
        return InscripcionService.inscribir_alumno_en_sesion(alumno, self.pk)


class InscripcionQuerySet(models.QuerySet):
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


class Inscripcion(models.Model):
    ESTADO_CONFIRMADA = 'confirmada'
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_CANCELADA = 'cancelada'

    ESTADOS_CHOICES = [
        (ESTADO_CONFIRMADA, 'Confirmada'),
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_CANCELADA, 'Cancelada'),
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

    def __str__(self):
        if self.sesion:
            return f'{self.alumno} inscrito en {self.clase} (Sesión #{self.sesion.pk})'
        return f'{self.alumno} inscrito en {self.clase}'


class SuscripcionQuerySet(models.QuerySet):
    def vigentes(self):
        return self.filter(estado=Suscripcion.ESTADO_ACTIVA, fecha_fin__gt=timezone.now())


class Suscripcion(models.Model):
    """Plan contratado por un alumno.

    Nace pendiente al iniciar Webpay y solo se activa cuando Transbank aprueba
    el pago (se busca por buy_order: la vuelta desde Webpay puede llegar sin la
    cookie de sesion). Es la unica fuente de verdad del plan: nada de localStorage.
    """
    # Los valores son los ids de los planes en el carrito (planes.html).
    PLAN_BASICO = '1'
    PLANES = [
        (PLAN_BASICO, 'Plan Básico'),
        ('2', 'Plan Medio'),
        ('3', 'Plan Superior'),
        ('5', 'Plan Personalizado'),
    ]
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ACTIVA = 'activa'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADOS = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ACTIVA, 'Aprobado'),
        (ESTADO_RECHAZADA, 'Rechazado'),
    ]

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name='suscripciones')
    plan = models.CharField(max_length=2, choices=PLANES)
    dias = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    monto = models.PositiveIntegerField()
    buy_order = models.CharField(max_length=26, db_index=True)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_PENDIENTE)
    creada = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)

    objects = SuscripcionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'
        ordering = ['-creada']

    def __str__(self):
        return f'{self.get_plan_display()} - {self.alumno} ({self.get_estado_display()})'

    @property
    def es_premium(self):
        return self.plan != self.PLAN_BASICO

    @classmethod
    def confirmar_pago(cls, buy_order, aprobado):
        """Activa o rechaza las suscripciones pendientes de la orden.

        Idempotente: si Webpay vuelve dos veces, la segunda no encuentra pendientes.
        """
        pendientes = cls.objects.filter(buy_order=buy_order, estado=cls.ESTADO_PENDIENTE)
        if not aprobado:
            pendientes.update(estado=cls.ESTADO_RECHAZADA)
            return
        ahora = timezone.now()
        for suscripcion in pendientes:
            suscripcion.estado = cls.ESTADO_ACTIVA
            suscripcion.fecha_fin = ahora + timedelta(days=suscripcion.dias)
            suscripcion.save(update_fields=['estado', 'fecha_fin'])


class Reporte(models.Model):
    id_reporte = models.AutoField(primary_key=True)
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    descripcion = models.TextField()
    fecha_reporte = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[('pendiente', 'Pendiente'), ('resuelto', 'Resuelto')], default='pendiente')

    def __str__(self):
        return f"Reporte de {self.remitente.first_name}"


class SolicitudRetiro(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='retiros')
    monto = models.IntegerField()
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[('pendiente', 'Pendiente'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado')], default='pendiente')
    banco = models.ForeignKey(Banco, on_delete=models.SET_NULL, null=True)
    tipo_cuenta = models.CharField(max_length=40, choices=[('rut_vista', 'Cuenta Rut / Vista'), ('corriente', 'Cuenta Corriente'), ('ahorro', 'Cuenta de Ahorro')], default='rut_vista')
    numero_cuenta = models.CharField(max_length=40, blank=True, default='')
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Retiro #{self.id_solicitud} - {self.profesor.user.first_name} (${self.monto})"


