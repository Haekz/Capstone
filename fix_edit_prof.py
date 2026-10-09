import os

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix edit profile for profesor
content = content.replace("profesor.especialidad = especialidad", '''from alumnos.models import Especialidad
            especialidad_obj, _ = Especialidad.objects.get_or_create(nombre=especialidad)
            profesor.especialidad = especialidad_obj''')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
