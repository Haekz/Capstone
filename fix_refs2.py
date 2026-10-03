import os
import re

directories = ['alumnos', 'user_profesor', 'admin_portal']
extensions = ['.py', '.html']

replacements = {
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.nombre\b': r'\1.user.first_name',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.rut\b': r'\1.user.rut',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.correo_electronico\b': r'\1.user.email',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.telefono\b': r'\1.user.telefono',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.direccion\b': r'\1.user.direccion',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.fecha_nacimiento\b': r'\1.user.fecha_nacimiento',
    r'\b(prof|admin_user|id_profesor|id_alumno|perfil_profesor)\.genero\b': r'\1.user.genero',
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
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
