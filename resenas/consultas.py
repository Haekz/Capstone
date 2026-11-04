"""Lo que muestran el perfil público y la página "Mis reseñas" del profesor."""

from django.db.models import Exists, OuterRef, Q

from alumnos.models import Inscripcion

from .models import MOTIVOS, Resena

RELACIONADAS = (
    'inscripcion__alumno__user',
    'inscripcion__clase__asignatura',
    'inscripcion__clase__profesor__user',
)


def pendiente_de_calificar(alumno):
    """La ultima clase completada del alumno cuya contratacion aun no tiene reseña, o None.

    Misma regla que ``Resena.objects.de_la_contratacion``: una reseña cubre el paquete o, sin paquete, la inscripcion."""
    ya_calificada = Resena.objects.filter(
        Q(paquete_id=OuterRef('paquete_id')) | Q(inscripcion=OuterRef('pk'), paquete__isnull=True))
    return (Inscripcion.objects.filter(alumno=alumno).completadas()
            .select_related('clase__asignatura', 'clase__profesor__user')
            .annotate(calificada=Exists(ya_calificada)).filter(calificada=False)
            .order_by('-sesion__fecha_hora_inicio').first())


def contexto_resenas(profesor, alumno_id=None, ruta_reporte=None):
    """Solo reseñas visibles, con su promedio. ``alumno_id`` marca las propias."""
    resenas = list(Resena.objects.visibles().de_profesor(profesor).select_related(*RELACIONADAS))
    for resena in resenas:
        resena.es_propia = resena.inscripcion.alumno_id == alumno_id
    total = len(resenas)
    # Coma decimal como en el resto del sitio (LANGUAGE_CODE es 'es-cl').
    promedio = f'{sum(r.puntaje for r in resenas) / total:.1f}'.replace('.', ',') if total else None
    return {
        'resenas': resenas,
        'total_resenas': total,
        'promedio': promedio,
        'ruta_reporte': ruta_reporte,
        'motivos': MOTIVOS,
    }
