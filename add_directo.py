import os

filepath = 'alumnos/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

view_code = '''
from django.views.decorators.http import require_POST

@require_POST
def iniciar_directo(request, clase_id):
    clase = get_object_or_404(Clase, id_clase=clase_id)
    
    # Solo el profesor de la clase puede iniciar
    profesor_id = request.session.get('profesor_id')
    if not profesor_id or str(clase.profesor.id_profesor) != str(profesor_id):
        return JsonResponse({'success': False, 'message': 'No tienes permiso.'})
        
    descripcion = request.POST.get('descripcion_vivo', '')
    temas = request.POST.get('temas_vivo', '')
    
    clase.descripcion_vivo = descripcion
    clase.temas_vivo = temas
    clase.en_vivo = True
    clase.save()
    
    return JsonResponse({'success': True})
'''

if 'def iniciar_directo' not in content:
    content += "\n" + view_code
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added iniciar_directo view")
else:
    print("View exists")
