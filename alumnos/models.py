from django.db import models

# Create your models here.

class Genero(models.Model):
    id_genero = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    def __str__(self):
        return self.descripcion

class Tutor(models.Model):
    id_tutor = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12)
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60)
    telefono = models.CharField(max_length=20, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

class Alumno(models.Model):
    id_alumno = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12)
    nivel_educacion = models.CharField(max_length=10, choices=[('basica', 'Básica'), ('media', 'Media'), ('superior', 'Superior')])
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60)
    telefono = models.CharField(max_length=20, blank=True)
    genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True)  
    id_tutor = models.ForeignKey(Tutor, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.nombre

class Profesor(models.Model):
    id_profesor = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=60)
    rut = models.CharField(max_length=12)
    especialidad = models.CharField(max_length=60)
    direccion = models.CharField(max_length=60)
    fecha_nacimiento = models.DateField()
    correo_electronico = models.EmailField(max_length=60)
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




