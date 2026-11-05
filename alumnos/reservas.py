"""Reservas del alumno: inscribirse a una clase, ver las sesiones con cupo, reservar,
cancelar y reprogramar."""

import json

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .decorators import alumno_required, alumno_required_json
from .exceptions import InscripcionError
from .models import Alumno, Inscripcion, SesionClase
from .services import InscripcionService


# ============================================================
# INSCRIPCIÓN DE CLASES
# ============================================================

@alumno_required_json
def inscribir_clase(request):

    alumno_id = request.session['alumno_id']

    if request.method == 'POST':

        try:

            alumno = get_object_or_404(
                Alumno,
                id_alumno=alumno_id
            )

            if request.content_type == 'application/json':

                data = json.loads(
                    request.body
                )

                id_clase = data.get(
                    'id_clase'
                )

            else:

                id_clase = request.POST.get(
                    'id_clase'
                )

            if not id_clase:

                return JsonResponse({
                    'success': False,
                    'message': (
                        'ID de clase no '
                        'proporcionado.'
                    )
                })

            from .services import InscripcionService
            from .exceptions import InscripcionError
            from django.core.exceptions import ValidationError

            inscripcion = InscripcionService.inscribir_alumno_en_clase(alumno, id_clase)

            return JsonResponse({
                'success': True,
                'message': (
                    f'¡Te has inscrito exitosamente a "{inscripcion.clase.asignatura.nombre}" '
                    f'con el profesor {inscripcion.clase.profesor.user.first_name}!'
                )
            })

        except (InscripcionError, ValidationError) as e:
            msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            return JsonResponse({
                'success': False,
                'message': msg
            })
        except Exception:
            return JsonResponse({
                'success': False,
                'message': 'Ocurrió un error inesperado al procesar la inscripción.'
            })

    return JsonResponse({
        'success': False,
        'message': 'Método no permitido.'
    })


@alumno_required_json
def listar_sesiones_disponibles(request):
    """Retorna las sesiones programadas a futuro con cupos libres en formato JSON."""
    clase_id = request.GET.get('clase_id')
    qs = SesionClase.objects.disponibles()
    if clase_id:
        qs = qs.filter(clase_id=clase_id)

    sesiones = (
        qs.select_related('clase', 'clase__asignatura', 'clase__profesor', 'clase__profesor__user')
        .order_by('fecha_hora_inicio')
    )

    inscritas_sesion_ids = set(
        Inscripcion.objects.filter(
            alumno_id=request.session['alumno_id'],
            sesion__isnull=False,
            estado__in=['confirmada', 'pendiente']
        )
        .values_list('sesion_id', flat=True)
    )

    data = [
        {
            'id_sesion': s.id_sesion,
            'id_clase': s.clase.id_clase,
            'asignatura': s.clase.asignatura.nombre,
            'profesor': s.clase.profesor.nombre,
            'modalidad': s.clase.modalidad,
            'fecha_hora_inicio': s.fecha_hora_inicio.isoformat(),
            'fecha_hora_fin': s.fecha_hora_fin.isoformat(),
            'fecha_formateada': s.inicio_local.strftime('%d/%m/%Y'),
            'hora_formateada': f"{s.inicio_local.strftime('%H:%M')} - {s.fin_local.strftime('%H:%M')} hrs",
            'inicio_formateado': s.inicio_local.strftime('%d/%m/%Y %H:%M'),
            'duracion_minutos': s.duracion_minutos,
            'cupo_maximo': s.cupo_maximo,
            'cupos_disponibles': s.cupos_disponibles,
            'precio': str(s.precio),
            'precio_formateado': f"${int(s.precio):,}".replace(',', '.') if s.precio > 0 else 'Gratis',
            'ya_inscrito': s.id_sesion in inscritas_sesion_ids,
        }
        for s in sesiones
    ]
    return JsonResponse({'success': True, 'sesiones': data})


@alumno_required_json
def reservar_sesion(request):
    """Endpoint para que un alumno autenticado reserve un cupo en una SesionClase puntual."""
    alumno_id = request.session['alumno_id']

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido.'}, status=405)

    try:
        alumno = get_object_or_404(Alumno, id_alumno=alumno_id)

        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8') or '{}')
            id_sesion = data.get('id_sesion')
        else:
            id_sesion = request.POST.get('id_sesion')

        if not id_sesion:
            return JsonResponse({'success': False, 'message': 'ID de sesión no proporcionado.'}, status=400)

        sesion = get_object_or_404(SesionClase, id_sesion=id_sesion)
        inscripcion = InscripcionService.inscribir_alumno_en_sesion(alumno, sesion.pk)

        return JsonResponse({
            'success': True,
            'message': (
                f'¡Reserva confirmada con éxito para la sesión de "{sesion.clase.asignatura.nombre}" '
                f'el {sesion.inicio_local.strftime("%d/%m/%Y a las %H:%M")}!'
            ),
            'id_inscripcion': inscripcion.pk
        })

    except Http404:
        return JsonResponse({'success': False, 'message': 'Sesión no encontrada.'}, status=404)
    except (InscripcionError, ValidationError) as e:
        msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
        return JsonResponse({'success': False, 'message': msg})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Error inesperado al procesar la reserva. Intenta nuevamente.'})


@alumno_required
def cancelar_inscripcion(request, pk):
    alumno_id = request.session['alumno_id']
    alumno = get_object_or_404(Alumno, id_alumno=alumno_id)
    inscripcion = get_object_or_404(Inscripcion, id_inscripcion=pk, alumno_id=alumno_id)

    # Protección contra CSRF: solo procesar cancelaciones reales por POST
    if request.method != 'POST':
        return redirect('alumno_pag1')

    from .services import InscripcionService
    try:
        InscripcionService.cancelar_inscripcion(alumno, inscripcion.pk)
    except InscripcionError:
        # Ya empezo o no esta activa: no se cancela, porque devolveria una clase ya tomada.
        pass

    return redirect('alumno_pag1')


@alumno_required
@require_POST
def reprogramar_inscripcion(request, pk):
    """Mueve una reserva propia a otra sesion del mismo profesor (POST id_sesion)."""
    alumno = get_object_or_404(Alumno, id_alumno=request.session['alumno_id'])
    id_sesion = request.POST.get('id_sesion', '')
    if not id_sesion.isdecimal():
        return JsonResponse({'success': False, 'message': 'ID de sesión no proporcionado.'}, status=400)
    try:
        inscripcion = InscripcionService.reprogramar_inscripcion(alumno, pk, int(id_sesion))
    except (InscripcionError, ValidationError) as e:
        return JsonResponse({'success': False, 'message': e.messages[0] if e.messages else str(e)})
    return JsonResponse({
        'success': True,
        'message': f'Reserva movida al {inscripcion.sesion.inicio_local.strftime("%d/%m/%Y a las %H:%M")}.',
    })
