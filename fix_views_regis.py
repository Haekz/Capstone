import os, re

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Profesor.objects.create in regis_prof
old_prof_create = '''            profesor = Profesor.objects.create(
                user=user,
                nombre=nombre,
                rut=rut,
                especialidad=especialidad,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero
            )'''

new_prof_create = '''            from alumnos.models import Especialidad
            especialidad_obj, _ = Especialidad.objects.get_or_create(nombre=especialidad)
            
            profesor = Profesor.objects.create(
                user=user,
                especialidad=especialidad_obj
            )'''

content = content.replace(old_prof_create, new_prof_create)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
