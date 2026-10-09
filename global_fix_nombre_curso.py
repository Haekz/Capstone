import os

replacements = {
    'admin_portal/templates/admin_portal/dashboard_admin.html': [
        ('{{ c.nombre_curso }}', '{{ c.asignatura.nombre }}')
    ],
    'admin_portal/views.py': [
        ('nombre_curso=nombre_curso,', 'asignatura=Asignatura.objects.get_or_create(nombre=nombre_curso)[0],'),
        ('clase.nombre_curso', 'clase.asignatura.nombre')
    ],
    'alumnos/templates/alumnos/Alumno_pag1.html': [
        ('{{ insc.clase.nombre_curso }}', '{{ insc.clase.asignatura.nombre }}'),
        ('{{ c.nombre_curso }}', '{{ c.asignatura.nombre }}')
    ],
    'alumnos/views.py': [
        ('clase.nombre_curso', 'clase.asignatura.nombre')
    ],
    'user_profesor/templates/user_profesor/clases_solicitadas.html': [
        ('{{ ins.clase.nombre_curso }}', '{{ ins.clase.asignatura.nombre }}')
    ],
    'user_profesor/templates/user_profesor/panel_profesor.html': [
        ('{{ ch.nombre_curso }}', '{{ ch.asignatura.nombre }}')
    ],
    'user_profesor/views.py': [
        ('clase.nombre_curso', 'clase.asignatura.nombre')
    ]
}

for filepath, reps in replacements.items():
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        for old, new in reps:
            content = content.replace(old, new)
        
        # for admin_portal/views.py, ensure Asignatura is imported
        if filepath == 'admin_portal/views.py' and 'Asignatura' not in content:
            content = content.replace('from alumnos.models import CustomUser, Tutor, Profesor, Clase', 'from alumnos.models import CustomUser, Tutor, Profesor, Clase, Asignatura')
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")
    else:
        print(f"Not found: {filepath}")
