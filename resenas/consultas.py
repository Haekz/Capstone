"""Lo que muestran el perfil público y la página "Mis reseñas" del profesor."""

from .models import MOTIVOS, Resena

RELACIONADAS = (
    'inscripcion__alumno__user',
    'inscripcion__clase__asignatura',
    'inscripcion__clase__profesor__user',
)


def contexto_resenas(profesor, alumno_id=None, ruta_reporte=None):
    """Solo reseñas visibles, con su promedio. ``alumno_id`` marca las propias."""
    resenas = list(Resena.objects.visibles().de_profesor(profesor).select_related(*RELACIONADAS))
    for resena in resenas:
        resena.es_propia = resena.inscripcion.alumno_id == alumno_id
    total = len(resenas)
    # Coma decimal como en el resto del sitio (LANGUAGE_CODE es 'en-us').
    promedio = f'{sum(r.puntaje for r in resenas) / total:.1f}'.replace('.', ',') if total else None
    return {
        'resenas': resenas,
        'total_resenas': total,
        'promedio': promedio,
        'ruta_reporte': ruta_reporte,
        'motivos': MOTIVOS,
    }
