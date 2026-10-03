import re

with open('alumnos/models.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'class Banco\(models\.Model\):(.*?)def __str__\(self\):.*?return self\.user\.first_name if self\.user else "Sin usuario"', r'class Banco(models.Model):\1def __str__(self):\n        return self.nombre', content, flags=re.DOTALL)
content = re.sub(r'class Especialidad\(models\.Model\):(.*?)def __str__\(self\):.*?return self\.user\.first_name if self\.user else "Sin usuario"', r'class Especialidad(models.Model):\1def __str__(self):\n        return self.nombre', content, flags=re.DOTALL)
content = re.sub(r'class Asignatura\(models\.Model\):(.*?)def __str__\(self\):.*?return self\.user\.first_name if self\.user else "Sin usuario"', r'class Asignatura(models.Model):\1def __str__(self):\n        return self.nombre', content, flags=re.DOTALL)

with open('alumnos/models.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
