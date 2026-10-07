import os

files = [
    'user_profesor/templates/user_profesor/clases_en_vivo.html',
    'alumnos/templates/alumnos/sala_virtual.html'
]

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace('{{ c.nombre_curso }}', '{{ c.asignatura.nombre }}')
    content = content.replace('{{ clase.nombre_curso }}', '{{ clase.asignatura.nombre }}')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
