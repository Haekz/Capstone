"""Datos de las tres pantallas que muestran observaciones: el profesor que las escribe, el alumno (menor o no) y el
apoderado del menor que las leen.

Privacidad: del alumno solo el nombre de pila, igual que la agenda del profesor.
"""

from alumnos.models import Inscripcion
from alumnos.utils import es_menor

from .models import Observacion, fecha_limite

LIMITE = 20  # clases realizadas que se listan al profesor: las mas recientes


def contexto_profesor(profesor):
    """Sus ultimas clases realizadas (dentro del plazo de conservacion), cada una con su observacion o vacia."""
    realizadas = (Inscripcion.objects.completadas().filter(clase__profesor=profesor,
                                                           sesion__fecha_hora_inicio__gte=fecha_limite())
                  .select_related('alumno__user', 'clase__asignatura', 'sesion', 'observacion')
                  .order_by('-sesion__fecha_hora_inicio')[:LIMITE])
    return {
        'clases_realizadas': [{
            'id': i.pk, 'alumno': i.alumno.user.first_name, 'asignatura': i.clase.asignatura.nombre,
            'fecha': i.sesion.inicio_local,
            'lee': 'el alumno y su apoderado' if es_menor(i.alumno.user) else 'el alumno',
            'texto': i.observacion.texto if hasattr(i, 'observacion') else '',
        } for i in realizadas],
        'observacion_maximo': Observacion.MAXIMO,
    }


def del_alumno(alumno):
    """Lo que recibio ``alumno``, listo para mostrar: se lo muestran a el mismo y, si es menor, tambien a su apoderado."""
    return [{'profesor': o.inscripcion.clase.profesor.nombre, 'asignatura': o.inscripcion.clase.asignatura.nombre,
             'fecha': o.inscripcion.sesion.inicio_local, 'texto': o.texto}
            for o in Observacion.objects.del_alumno(alumno)]
