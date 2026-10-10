import os

filepath = 'user_profesor/views.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re

old_block = '''            if not all([nombre, rut, especialidad, direccion, correo, telefono, genero_id]):
                return JsonResponse({"success": False, "message": "Todos los campos son obligatorios."})

            genero = get_object_or_404(Genero, id_genero=genero_id)

            profesor.user.first_name = nombre
            profesor.user.rut = rut
            from alumnos.models import Especialidad
            especialidad_obj, _ = Especialidad.objects.get_or_create(nombre=especialidad)
            profesor.especialidad = especialidad_obj
            profesor.user.direccion = direccion
            profesor.user.email = correo
            profesor.user.telefono = telefono
            profesor.user.genero = genero
            profesor.user.save()
            profesor.save()

            return JsonResponse({"success": True, "message": "Perfil actualizado correctamente."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})'''

new_block = '''            if not all([nombre, rut, especialidad, direccion, correo, telefono, genero_id]):
                return JsonResponse({"success": False, "message": "Todos los campos son obligatorios."})

            genero = get_object_or_404(Genero, id_genero=genero_id)
            
            partes = nombre.split(' ', 1)
            profesor.user.first_name = partes[0]
            profesor.user.last_name = partes[1] if len(partes) > 1 else ''

            profesor.user.rut = rut
            from alumnos.models import Especialidad
            especialidad_obj, _ = Especialidad.objects.get_or_create(nombre=especialidad)
            profesor.especialidad = especialidad_obj
            profesor.user.direccion = direccion
            profesor.user.email = correo
            profesor.user.telefono = telefono
            profesor.user.genero = genero
            
            # Nuevos campos
            profesor.telefono_publico = request.POST.get('telefono_publico') == 'on'
            if 'foto_perfil' in request.FILES:
                profesor.user.foto_perfil = request.FILES['foto_perfil']
                
            profesor.user.save()
            profesor.save()

            return JsonResponse({"success": True, "message": "Perfil actualizado correctamente."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})'''

content = content.replace(old_block, new_block)
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated views")
