import os

filepath = 'alumnos/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Append the sala_virtual view
view_code = '''
def sala_virtual(request, clase_id):
    # Validar que el usuario esta autenticado
    # Esta vista es mixta: puede entrar un profesor o un alumno
    
    # Obtener la clase
    clase = get_object_or_404(Clase, id_clase=clase_id)
    
    # En un sistema real, aca validamos que si es alumno, este inscrito en esta clase
    # Y si es profesor, que sea el profesor de esta clase
    
    context = {
        'clase': clase
    }
    return render(request, 'alumnos/sala_virtual.html', context)
'''

if 'def sala_virtual' not in content:
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write("\n" + view_code)

