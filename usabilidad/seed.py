"""Datos de demo para las pruebas de usabilidad (10.2).

Se ejecuta contra una base SQLite aparte (usab.sqlite3) via
DJANGO_SETTINGS_MODULE=usabilidad.settings_usab, asi la base real no se toca.
Uso: python manage.py shell -c "exec(open('usabilidad/seed.py', encoding='utf-8').read())"
(no usar 'shell < seed.py' en Windows: la consola cp1252 rompe las tildes)
"""
from datetime import date, time

from django.contrib.auth import get_user_model

from alumnos.models import Alumno, Clase, Genero, Profesor, Tutor

User = get_user_model()
CLAVE = 'Demo12345!'

g, _ = Genero.objects.get_or_create(descripcion='Femenino')
Genero.objects.get_or_create(descripcion='Masculino')
Genero.objects.get_or_create(descripcion='Otro')


def usuario(rut, nombre, correo, rol):
    u, creado = User.objects.get_or_create(
        username=rut, defaults=dict(rut=rut, email=correo, rol=rol, first_name=nombre)
    )
    if creado:
        u.set_password(CLAVE)
        u.save()
    return u


ua = usuario('11111111-1', 'Ana Alumna', 'ana@demo.cl', 'alumno')
Alumno.objects.get_or_create(user=ua, defaults=dict(
    nombre='Ana Alumna', rut='11111111-1', nivel_educacion='media', direccion='Santiago',
    fecha_nacimiento=date(2007, 5, 1), correo_electronico='ana@demo.cl', telefono='911111111', genero=g))

profes = [
    ('22222222-2', 'Pedro Soto', 'Matemáticas'),
    ('12345678-5', 'Carla Díaz', 'Inglés'),
    ('9876543-3', 'Luis Rojas', 'Física'),
]
for rut, nombre, esp in profes:
    up = usuario(rut, nombre, f'{nombre.split()[0].lower()}@demo.cl', 'profesor')
    p, _ = Profesor.objects.get_or_create(user=up, defaults=dict(
        nombre=nombre, rut=rut, especialidad=esp, direccion='Santiago',
        fecha_nacimiento=date(1988, 1, 1), correo_electronico=up.email, telefono='922222222', genero=g,
        titulo_estado=Profesor.TITULO_APROBADO))
    Clase.objects.get_or_create(nombre_curso=f'{esp} básico', id_profesor=p,
                                defaults=dict(modalidad='online', horario=time(17, 0)))

ut = usuario('33333333-3', 'Tania Admin', 'tania@demo.cl', 'admin')
Tutor.objects.get_or_create(user=ut, defaults=dict(
    nombre='Tania Admin', rut='33333333-3', direccion='Santiago',
    fecha_nacimiento=date(1985, 1, 1), correo_electronico='tania@demo.cl', genero=g))

print('SEED OK')
