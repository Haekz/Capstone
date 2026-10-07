import os

filepath = 'alumnos/backends.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''
        # 2. Si no se encuentra en User, buscar en los perfiles por variantes de RUT
        if not users.exists():
            from alumnos.models import Alumno, Profesor, Tutor

            alumno = Alumno.objects.filter(rut__in=ruts).select_related('user').first()
            if alumno and alumno.user:
                users = User.objects.filter(pk=alumno.user.pk)
            else:
                profesor = Profesor.objects.filter(rut__in=ruts).select_related('user').first()
                if profesor and profesor.user:
                    users = User.objects.filter(pk=profesor.user.pk)
                else:
                    tutor = Tutor.objects.filter(rut__in=ruts).select_related('user').first()
                    if tutor and tutor.user:
                        users = User.objects.filter(pk=tutor.user.pk)
'''
new = ""

content = content.replace(old, new)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed backend")
