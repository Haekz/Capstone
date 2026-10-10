from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

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


class Clase(models.Model):
    id_clase = models.AutoField(primary_key=True)
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE)
    modalidad = models.CharField(max_length=10, choices=[('online', 'Online'), ('presencial', 'Presencial')])
    horario = models.TimeField()
    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    en_vivo = models.BooleanField(default=False)
    descripcion_vivo = models.TextField(blank=True, null=True)
    temas_vivo = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.asignatura.nombre} - {self.profesor.user.first_name}"


class Inscripcion(models.Model):
    id_inscripcion = models.AutoField(primary_key=True)
    fecha_inscripcion = models.DateField(auto_now_add=True)
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.alumno} inscrito en {self.clase}'


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


