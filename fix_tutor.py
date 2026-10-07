import re

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Tutor.objects.create(...)
old = '''            tutor = Tutor.objects.create(
                user=user,
                nombre=nombre,
                rut=rut,
                direccion=direccion,
                fecha_nacimiento=fecha_nacimiento,
                correo_electronico=correo_electronico,
                telefono=telefono,
                genero=genero_obj
            )'''
new = '''            tutor = Tutor.objects.create(
                user=user
            )'''

content = content.replace(old, new)

# And what about SolicitudRetiro in user_profesor/views.py ?
# SolicitudRetiro.objects.create(..., banco=banco if banco else 'Banco Estado') -> banco should be an instance of Banco!
# Let's fix that too.
old_sr = '''            SolicitudRetiro.objects.create(
                profesor=profesor,
                monto=monto,
                banco=banco if banco else 'Banco Estado',
                tipo_cuenta=tipo_cuenta,
                numero_cuenta=numero_cuenta
            )'''
new_sr = '''            from alumnos.models import Banco
            banco_obj, _ = Banco.objects.get_or_create(nombre=banco if banco else 'Banco Estado')
            SolicitudRetiro.objects.create(
                profesor=profesor,
                monto=monto,
                banco=banco_obj,
                tipo_cuenta=tipo_cuenta,
                numero_cuenta=numero_cuenta
            )'''

content = content.replace(old_sr, new_sr)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed user_profesor/views.py Tutor create and SolicitudRetiro")
