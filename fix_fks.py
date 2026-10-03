import os
import re

directories = ['alumnos', 'user_profesor', 'admin_portal']
extensions = ['.py', '.html']

replacements = [
    # templates
    (r'\.id_clase\.', r'.clase.'),
    (r'\.id_profesor\.', r'.profesor.'),
    (r'\.id_alumno\.', r'.alumno.'),
    
    # views - queries and creates
    (r'id_alumno=alumno\b', r'alumno=alumno'),
    (r'id_clase=clase\b', r'clase=clase'),
    (r'id_profesor=profesor\b', r'profesor=profesor'),
    
    # query lookups
    (r'id_clase__id_profesor', r'clase__profesor'),
    (r'id_clase__profesor', r'clase__profesor'),
    
    # Other filter assignments where they pass objects or IDs
    (r'id_profesor=id_profesor', r'profesor_id=id_profesor'),
    (r'id_alumno=alumno_id', r'alumno_id=alumno_id'),
    
    # in user_profesor views.py:
    (r'id_clase__in', r'clase_id__in'),
    (r'id_clase=id_clase', r'clase_id=id_clase'),
]

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = re.sub(old, new, new_content)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for d in directories:
    for root, dirs, files in os.walk(d):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                process_file(os.path.join(root, file))
print('Done!')
