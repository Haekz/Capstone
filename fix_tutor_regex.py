import re

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix Tutor.objects.create
content = re.sub(
    r'tutor\s*=\s*Tutor\.objects\.create\(\s*user=user,\s*nombre=nombre,\s*rut=rut,\s*direccion=direccion,\s*fecha_nacimiento=fecha_nacimiento,\s*correo_electronico=correo_electronico,\s*telefono=telefono,\s*genero=genero_obj\s*\)',
    r'tutor = Tutor.objects.create(user=user)',
    content
)

# Fix SolicitudRetiro.objects.create
content = re.sub(
    r'SolicitudRetiro\.objects\.create\(\s*profesor=profesor,\s*monto=monto,\s*banco=banco if banco else \'Banco Estado\',\s*tipo_cuenta=tipo_cuenta if tipo_cuenta else \'Cuenta Rut / Vista\',\s*numero_cuenta=numero_cuenta\s*\)',
    r"from alumnos.models import Banco\n            banco_obj, _ = Banco.objects.get_or_create(nombre=banco if banco else 'Banco Estado')\n            SolicitudRetiro.objects.create(\n                profesor=profesor,\n                monto=monto,\n                banco=banco_obj,\n                tipo_cuenta=tipo_cuenta if tipo_cuenta else 'Cuenta Rut / Vista',\n                numero_cuenta=numero_cuenta\n            )",
    content
)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex fix applied")
