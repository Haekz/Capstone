import os, re

def clean_kwargs(match):
    # match.group(0) is the entire Alumno.objects.create(...)
    call = match.group(0)
    # Remove bad kwargs
    bad_keys = ['nombre', 'rut', 'direccion', 'fecha_nacimiento', 'correo_electronico', 'telefono', 'genero']
    for key in bad_keys:
        call = re.sub(r",\s*" + key + r"\s*=\s*[^,)]*", "", call)
    
    # Fix especialidad='...'
    call = re.sub(r"especialidad\s*=\s*'([^']+)'", r"especialidad=Especialidad.objects.get_or_create(nombre='\1')[0]", call)
    
    return call

for root, dirs, files in os.walk('.'):
    if 'migrations' in root or '.venv' in root or 'Lib' in root: continue
    for file in files:
        if (file.startswith('test') and file.endswith('.py')) or file == 'tests.py':
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            if 'Especialidad' not in content:
                content = 'from alumnos.models import Especialidad\n' + content

            content = re.sub(r"(Alumno|Profesor|Tutor)\.objects\.create\([^)]+\)", clean_kwargs, content)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {path}")
