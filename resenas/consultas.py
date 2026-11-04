"""Lo que muestran el perfil público y la página "Mis reseñas" del profesor."""

from django.db.models import Avg, Count, Exists, OuterRef, Q

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


def formatear_promedio(promedio):
    """Una decimal y coma, como en el resto del sitio (LANGUAGE_CODE es 'es-cl')."""
    return f'{promedio:.1f}'.replace('.', ',')


def calificaciones_por_profesor():
    """``{id_profesor: {'promedio': 4.5, 'total': 2}}`` con las reseñas visibles, en una sola consulta.

    Sin reseñas el profesor no aparece. ``order_by()`` vacio: Resena ordena por fecha y eso agruparia por ella."""
    filas = (Resena.objects.visibles().order_by().values('inscripcion__clase__profesor')
             .annotate(promedio=Avg('puntaje'), total=Count('pk')))
    return {fila['inscripcion__clase__profesor']: {'promedio': fila['promedio'], 'total': fila['total']}
            for fila in filas}


def contexto_resenas(profesor, alumno_id=None, ruta_reporte=None):
    """Solo reseñas visibles, con su promedio. ``alumno_id`` marca las propias."""
    resenas = list(Resena.objects.visibles().de_profesor(profesor).select_related(*RELACIONADAS))
    for resena in resenas:
        resena.es_propia = resena.inscripcion.alumno_id == alumno_id
    total = len(resenas)
    promedio = formatear_promedio(sum(r.puntaje for r in resenas) / total) if total else None
    return {
        'resenas': resenas,
        'total_resenas': total,
        'promedio': promedio,
        'ruta_reporte': ruta_reporte,
        'motivos': MOTIVOS,
    }
