import sys

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'SolicitudRetiro.objects.create(' in line:
        new_lines.append("            from alumnos.models import Banco\n")
        new_lines.append("            banco_obj, _ = Banco.objects.get_or_create(nombre=banco if banco else 'Banco Estado')\n")
        new_lines.append(line)
        new_lines.append('                profesor=profesor,\n')
        new_lines.append('                monto=monto,\n')
        new_lines.append('                banco=banco_obj,\n')
        new_lines.append("                tipo_cuenta=tipo_cuenta if tipo_cuenta else 'Cuenta Rut / Vista',\n")
        new_lines.append('                numero_cuenta=numero_cuenta\n')
        new_lines.append('            )\n')
        skip = True
        continue
    
    if skip:
        if line.strip() == ')':
            skip = False
        continue
        
    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(''.join(new_lines))

print("Line replacement done for SolicitudRetiro.")
