import os

filepath = 'alumnos/models.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Add foto_perfil to CustomUser
if 'foto_perfil' not in content:
    content = content.replace(
        "genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True, blank=True)",
        "genero = models.ForeignKey(Genero, on_delete=models.SET_NULL, null=True, blank=True)\n    foto_perfil = models.ImageField(upload_to='perfiles/', null=True, blank=True)"
    )

# Add telefono_publico to Profesor
if 'telefono_publico' not in content:
    content = content.replace(
        "especialidad = models.ForeignKey(Especialidad, on_delete=models.SET_NULL, null=True)",
        "especialidad = models.ForeignKey(Especialidad, on_delete=models.SET_NULL, null=True)\n    telefono_publico = models.BooleanField(default=False, help_text='¿Mostrar teléfono a los alumnos?')"
    )

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
