from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Genero(models.Model):
    id_genero = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    def __str__(self):
        return self.descripcion

class Tutor(models.Model):
    id_tutor = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_tutor', null=True, blank=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12, unique=True)
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

class Alumno(models.Model):
    id_alumno = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_alumno', null=True, blank=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12, unique=True)
    nivel_educacion = models.CharField(max_length=10, choices=[('basica', 'Básica'), ('media', 'Media'), ('superior', 'Superior')])
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60, unique=True)
    telefono = models.CharField(max_length=20, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True)  
    id_tutor = models.ForeignKey(Tutor, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

class Profesor(models.Model):
    id_profesor = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil_profesor', null=True, blank=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12, unique=True)
    especialidad = models.CharField(max_length=60)
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60, unique=True)
    telefono = models.CharField(max_length=20)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

class Clase(models.Model):
    id_clase = models.AutoField(primary_key=True)
    nombre_curso = models.CharField(max_length=60)
    modalidad = models.CharField(max_length=10, choices=[('online', 'Online'), ('presencial', 'Presencial')])
    horario = models.TimeField()
    id_profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre_curso

class Inscripcion(models.Model):
    id_inscripcion = models.AutoField(primary_key=True)
    fecha_inscripcion = models.DateField(auto_now_add=True)
    id_alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    id_clase = models.ForeignKey(Clase, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.id_alumno.nombre} inscrito en {self.id_clase.nombre_curso}'


class Reporte(models.Model):
    id_reporte = models.AutoField(primary_key=True)
    remitente_tipo = models.CharField(max_length=15, choices=[('alumno', 'Alumno'), ('profesor', 'Profesor')])
    remitente_nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    fecha_reporte = models.DateField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[('pendiente', 'Pendiente'), ('resuelto', 'Resuelto')], default='pendiente')

    def __str__(self):
        return f"Reporte de {self.remitente_nombre} ({self.remitente_tipo})"


class SolicitudRetiro(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    id_profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE, related_name='retiros')
    monto = models.IntegerField()
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=15, choices=[('pendiente', 'Pendiente'), ('aprobado', 'Aprobado'), ('rechazado', 'Rechazado')], default='pendiente')
    banco = models.CharField(max_length=60, default='Banco Estado')
    tipo_cuenta = models.CharField(max_length=40, default='Cuenta Rut / Vista')
    numero_cuenta = models.CharField(max_length=40, blank=True, default='')
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Retiro #{self.id_solicitud} - {self.id_profesor.nombre} (${self.monto}) - {self.estado}"




