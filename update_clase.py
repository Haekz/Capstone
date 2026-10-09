import os

filepath = 'alumnos/models.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

if 'en_vivo = models.BooleanField' not in content:
    # Insert new fields into Clase
    old = '    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)'
    new = '''    profesor = models.ForeignKey(Profesor, on_delete=models.CASCADE)
    en_vivo = models.BooleanField(default=False)
    descripcion_vivo = models.TextField(blank=True, null=True)
    temas_vivo = models.CharField(max_length=255, blank=True, null=True)'''
    content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added fields to Clase")
else:
    print("Fields already exist")
