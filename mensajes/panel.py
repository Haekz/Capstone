"""Datos del Buzon de los paneles de profesor y alumno (paso C1b). Solo nombres de pila (privacidad)."""

from alumnos.models import Profesor
from alumnos.utils import es_menor

from . import servicio
from .models import Conversacion

MAX_VISIBLES = 200


def _mensajes_de(conversacion):
    recientes = conversacion.mensajes.order_by('-creado', '-pk')[:MAX_VISIBLES]
    return list(recientes)[::-1]


def contexto_profesor(profesor, activa_id):
    """Sus conversaciones y, si pidio una (?c=), sus mensajes; abrirla la marca como leida."""
    conversaciones = list(Conversacion.objects.filter(profesor=profesor).select_related('alumno__user')
                          .bandeja(profesor.user, 'visto_profesor'))
    activa = next((c for c in conversaciones if str(c.pk) == str(activa_id)), None)
    mensajes = []
    if activa:
        mensajes = _mensajes_de(activa)
        servicio.marcar_visto(profesor.user, activa)
        activa.sin_leer = False
    return {'buzon': conversaciones, 'buzon_activa': activa, 'buzon_mensajes': mensajes}


def contexto_alumno(alumno, activa_id, error=None):
    """Lo mismo para el alumno adulto, mas los profesores a quienes aun puede escribir.

    Un menor no tiene mensajes: su contexto va vacio."""
    vacio = {'bandeja': [], 'bandeja_activa': None, 'bandeja_mensajes': [], 'bandeja_nuevos': [],
             'bandeja_error': error}
    if es_menor(alumno.user):
        return vacio
    conversaciones = list(Conversacion.objects.filter(alumno=alumno, cliente=alumno.user)
                          .select_related('profesor__user', 'profesor__especialidad')
                          .bandeja(alumno.user, 'visto_cliente'))
    activa = next((c for c in conversaciones if str(c.pk) == str(activa_id)), None)
    mensajes = []
    if activa:
        mensajes = _mensajes_de(activa)
        servicio.marcar_visto(alumno.user, activa)
        activa.sin_leer = False
    sin_conversacion = servicio.ids_profesores_con_relacion(alumno) - {c.profesor_id for c in conversaciones}
    nuevos = Profesor.objects.filter(pk__in=sin_conversacion).select_related('user', 'especialidad')
    return {**vacio, 'bandeja': conversaciones, 'bandeja_activa': activa, 'bandeja_mensajes': mensajes,
            'bandeja_nuevos': list(nuevos)}
