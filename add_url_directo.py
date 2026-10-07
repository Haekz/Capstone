import os

filepath = 'alumnos/urls.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'iniciar_directo' not in content:
    content = content.replace('sala_virtual,', 'sala_virtual,\n    iniciar_directo,')
    content = content.replace("name='sala_virtual'),", "name='sala_virtual'),\n    path('sala-virtual/<int:clase_id>/iniciar/', iniciar_directo, name='iniciar_directo'),")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added iniciar_directo url")
