import os

filepath = 'alumnos/urls.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the broken path
bad_path = '''    path('sala-virtual/<int:clase_id>/', sala_virtual,
    iniciar_directo, name='sala_virtual'),'''
good_path = '''    path('sala-virtual/<int:clase_id>/', sala_virtual, name='sala_virtual'),'''

content = content.replace(bad_path, good_path)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed URLs")
