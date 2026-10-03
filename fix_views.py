import os
import re

filepath = 'alumnos/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Alumno PK query
content = content.replace('alumno_id=alumno_id', 'id_alumno=alumno_id')

# Fix select_related
content = content.replace("select_related(\n        'id_profesor'", "select_related(\n        'profesor'")
content = content.replace("select_related(\n            'id_clase'", "select_related(\n            'clase'")

# Fix values_list
content = content.replace("values_list(\n            'id_clase_id'", "values_list(\n            'clase_id'")

# Also fix get_object_or_404(Inscripcion) in eliminar_inscripcion
content = content.replace('id_alumno_id=alumno_id', 'alumno_id=alumno_id')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
