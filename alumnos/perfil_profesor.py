"""SCRUM-32: perfil profesional del profesor que ven los alumnos.

Privacidad:
- Solo profesores habilitados (titulo aprobado); el resto responde 404.
- Se muestran datos profesionales: nombre, especialidad, titulo verificado,
  clases y proximas sesiones.
- El telefono solo si el profesor lo autorizo (Profesor.telefono_publico).
- Nunca RUT, correo, direccion, fecha de nacimiento ni el archivo del titulo.
"""

from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .decorators import alumno_required
from .models import Clase, Profesor, SesionClase

MAX_PROXIMAS_SESIONES = 5


@never_cache
@alumno_required
def perfil_profesor(request, id_profesor):
    profesor = get_object_or_404(
        Profesor.objects.habilitados().select_related('user', 'especialidad'),
        id_profesor=id_profesor,
    )
    sesiones = SesionClase.objects.filter(clase__profesor=profesor)
    return render(request, 'alumnos/perfil_profesor.html', {
        'profesor': profesor,
        'telefono': profesor.user.telefono if profesor.telefono_publico else '',
        'clases': (
            Clase.objects.filter(profesor=profesor)
            .select_related('asignatura').order_by('asignatura__nombre')
        ),
        'proximas_sesiones': (
            sesiones.disponibles().select_related('clase__asignatura')
            .order_by('fecha_hora_inicio')[:MAX_PROXIMAS_SESIONES]
        ),
        'sesiones_realizadas': (
            sesiones.filter(fecha_hora_fin__lte=timezone.now())
            .exclude(estado=SesionClase.ESTADO_CANCELADA).count()
        ),
    })
