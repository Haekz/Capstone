"""Cuentas y perfiles: usuario, tutor (admin), alumno y profesor, con sus catalogos."""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator

from .. import liquidacion, paquetes


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
        ('apoderado', 'Apoderado'),
        ('soporte', 'Soporte'),
    )
    rol = models.CharField(max_length=15, choices=ROLES, default='alumno')
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.CharField(max_length=100, blank=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True, blank=True)
    foto_perfil = models.ImageField(upload_to='perfiles/', null=True, blank=True)
    # Cuenta suprimida (mensajes/supresion.py): la fila se conserva, sin datos personales, solo porque tiene
    # conversaciones reportadas retenidas. Nunca vuelve a entrar.
    suprimida = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_rol_display()})"


class Tutor(models.Model):
    # Perfil del ADMINISTRADOR (ver roles.ADMIN), no un tutor legal: no reutilizar
    # para apoderados de menores, porque tener este perfil abre el portal admin.
    id_tutor = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_tutor')

    def __str__(self):
        return f"Tutor: {self.user.first_name} {self.user.last_name}"


class Alumno(models.Model):
    id_alumno = models.AutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_alumno')
    nivel_educacion = models.CharField(max_length=10, choices=[('basica', 'Básica'), ('media', 'Media'), ('superior', 'Superior')])

    def __str__(self):
        return f"Alumno: {self.user.first_name} {self.user.last_name}"

    def resumen_progreso(self):
        """Horas, clases y ramos de las clases que el alumno ya completo (vista Mi Progreso)."""
        completadas = list(
            self.inscripcion_set.completadas().select_related('sesion', 'clase')
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

    # Documento privado (paso 9b): cifrado en la base, como los de apoderados. Soporte lo ve como imagen
    # con marca de agua (admin_portal.ver_titulo) y se borra al aprobarlo o rechazarlo.
    titulo_contenido = models.BinaryField(null=True, blank=True)
    titulo_formato = models.CharField(max_length=4, blank=True)  # JPEG, PNG o PDF
    # Antes del paso 9b: en disco y sin cifrar. manage.py pasar_titulos_a_base los mueve; luego se quita.
    titulo_archivo = models.FileField(upload_to='titulos/', blank=True)
    titulo_estado = models.CharField(max_length=12, choices=ESTADOS_TITULO, default=TITULO_PENDIENTE)
    titulo_observacion = models.CharField(max_length=200, blank=True)
    titulo_actualizado = models.DateTimeField(null=True, blank=True)
    # Valor de una clase de 60 min; de aqui salen los precios de los paquetes.
    tarifa = models.PositiveIntegerField(
        default=paquetes.TARIFA_BASE,
        validators=[MinValueValidator(paquetes.TARIFA_MIN), MaxValueValidator(paquetes.TARIFA_MAX)],
        help_text='Valor de una clase de 60 minutos, en pesos.',
    )
    # Ciclo de pago (alumnos/liquidacion.py). Un cambio rige desde frecuencia_nueva_desde.
    frecuencia_pago = models.CharField(max_length=10, choices=liquidacion.FRECUENCIAS, default=liquidacion.SEMANAL)
    frecuencia_nueva = models.CharField(max_length=10, choices=liquidacion.FRECUENCIAS, blank=True, default='')
    frecuencia_nueva_desde = models.DateField(null=True, blank=True)

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
