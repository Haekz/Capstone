"""Sala virtual de una clase (Jitsi): quien entra y el profesor que inicia el directo."""

from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apoderados.permisos import clase_pagada_por_apoderado

from .decorators import profesor_required_json, sesion_iniciada_required
from .models import Clase, Inscripcion
from .roles import PROFESOR, rol_en_sesion
from .utils import es_menor


def es_profesor_habilitado_de(clase, user):
    """El titular de la clase, con su titulo aprobado (SCRUM-87)."""
    return clase.profesor.user_id == user.id and clase.profesor.puede_hacer_clases


def nombre_sala_jitsi(clase):
    """Nombre de la sala en meet.jit.si, imposible de adivinar sin SECRET_KEY.

    meet.jit.si es publico: con un nombre predecible ('lbwus-clase-privada-5')
    cualquiera entraba directo, sin pasar por ``sala_virtual``.
    """
    return 'lbwus-' + salted_hmac('lbwus.sala_virtual', str(clase.id_clase)).hexdigest()[:32]


@never_cache
@sesion_iniciada_required
def sala_virtual(request, clase_id):
    clase = get_object_or_404(
        Clase.objects.select_related('asignatura', 'profesor', 'profesor__user', 'profesor__especialidad'),
        id_clase=clase_id
    )

    # Se decide por la cuenta (request.user), no por las claves de sesion:
    # 1. Profesor titular de la clase, con titulo aprobado.
    es_profesor = es_profesor_habilitado_de(clase, request.user)
    # 2. Alumno con una inscripcion que permita entrar (Inscripcion.puede_unirse).
    #    Menores: solo clases pagadas por su apoderado con vinculo vigente.
    menor = es_menor(request.user)
    es_alumno = not es_profesor and any(
        insc.puede_unirse and (not menor or clase_pagada_por_apoderado(insc))
        for insc in Inscripcion.objects.filter(alumno__user=request.user, clase=clase).select_related('sesion', 'alumno')
    )
    # Nadie mas entra: ni administradores, ni staff, ni el campo ``rol`` (SCRUM-87).
    if not (es_profesor or es_alumno):
        return HttpResponseForbidden("Acceso denegado: debes estar inscrito activamente en la clase o ser el profesor asignado.")

    context = {
        'clase': clase,
        'es_profesor': es_profesor,
        # Iniciar el directo es un POST con @profesor_required_json: el boton
        # solo aparece con el rol profesor activo (los demas esperan el directo).
        'puede_iniciar': es_profesor and rol_en_sesion(request) is PROFESOR,
        'sala_jitsi': nombre_sala_jitsi(clase),
    }
    return render(request, 'alumnos/sala_virtual.html', context)


@profesor_required_json
@require_POST
def iniciar_directo(request, clase_id):
    clase = get_object_or_404(Clase.objects.select_related('profesor'), id_clase=clase_id)

    # Solo el profesor titular de la clase, con titulo aprobado, puede iniciar
    if not es_profesor_habilitado_de(clase, request.user):
        return JsonResponse({'success': False, 'message': 'No tienes permiso.'}, status=403)

    descripcion = request.POST.get('descripcion_vivo', '').strip()[:2000]
    temas = request.POST.get('temas_vivo', '').strip()[:255]

    clase.descripcion_vivo = descripcion
    clase.temas_vivo = temas
    clase.en_vivo = True
    clase.save(update_fields=['descripcion_vivo', 'temas_vivo', 'en_vivo'])

    return JsonResponse({'success': True})
