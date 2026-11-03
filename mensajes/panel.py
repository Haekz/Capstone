"""Datos del Buzon de los paneles de profesor, alumno y apoderado (C1b y C2). Solo nombres de pila (privacidad)."""

from alumnos.models import Profesor
from alumnos.utils import es_menor
from apoderados.models import Vinculo

from . import servicio
from .models import Conversacion

MAX_VISIBLES = 200


def _mensajes_de(conversacion):
    recientes = conversacion.mensajes.order_by('-creado', '-pk')[:MAX_VISIBLES]
    return list(recientes)[::-1]


def _activa_y_mensajes(user, conversaciones, activa_id):
    """La conversacion pedida (?c=) entre las de `user`, con sus mensajes; abrirla la marca como leida.
    `solo_lectura`: ya no se puede escribir en ella (vinculo del apoderado terminado)."""
    activa = next((c for c in conversaciones if str(c.pk) == str(activa_id)), None)
    if activa is None:
        return None, []
    mensajes = _mensajes_de(activa)
    servicio.marcar_visto(user, activa)
    activa.sin_leer = False
    activa.solo_lectura = servicio.es_solo_lectura(activa)
    return activa, mensajes


def contexto_profesor(profesor, activa_id):
    """Sus conversaciones y, si pidio una (?c=), sus mensajes."""
    conversaciones = list(Conversacion.objects.visibles().filter(profesor=profesor).select_related('alumno__user')
                          .prefetch_related('alumno__vinculos_apoderado__apoderado')  # "Madre/Padre/Tutor legal de X"
                          .bandeja(profesor.user, 'visto_profesor'))
    activa, mensajes = _activa_y_mensajes(profesor.user, conversaciones, activa_id)
    return {'buzon': conversaciones, 'buzon_activa': activa, 'buzon_mensajes': mensajes}


def contexto_alumno(alumno, activa_id, error=None):
    """Lo mismo para el alumno adulto, mas los profesores a quienes aun puede escribir.

    Un menor no tiene mensajes: su contexto va vacio."""
    vacio = {'bandeja': [], 'bandeja_activa': None, 'bandeja_mensajes': [], 'bandeja_nuevos': [],
             'bandeja_error': error}
    if es_menor(alumno.user):
        return vacio
    conversaciones = list(Conversacion.objects.visibles().filter(alumno=alumno, cliente=alumno.user)
                          .select_related('profesor__user', 'profesor__especialidad')
                          .bandeja(alumno.user, 'visto_cliente'))
    activa, mensajes = _activa_y_mensajes(alumno.user, conversaciones, activa_id)
    sin_conversacion = servicio.ids_profesores_con_relacion(alumno) - {c.profesor_id for c in conversaciones}
    nuevos = Profesor.objects.filter(pk__in=sin_conversacion).select_related('user', 'especialidad')
    return {**vacio, 'bandeja': conversaciones, 'bandeja_activa': activa, 'bandeja_mensajes': mensajes,
            'bandeja_nuevos': list(nuevos)}


def contexto_apoderado(apoderado, activa_id):
    """Las conversaciones del apoderado (cada una, sobre un estudiante) y, por cada estudiante con vinculo
    vigente, los profesores a quienes aun no ha escrito. Las de un vinculo terminado siguen visibles."""
    conversaciones = list(Conversacion.objects.visibles().filter(cliente=apoderado.user)
                          .select_related('alumno__user', 'profesor__user', 'profesor__especialidad')
                          .bandeja(apoderado.user, 'visto_cliente'))
    activa, mensajes = _activa_y_mensajes(apoderado.user, conversaciones, activa_id)
    hablados = {(c.alumno_id, c.profesor_id) for c in conversaciones}
    nuevos = []
    for vinculo in apoderado.vinculos.filter(estado=Vinculo.VERIFICADO).select_related('alumno__user'):
        if not vinculo.autoriza(vinculo.alumno):
            continue
        ids = servicio.ids_profesores_con_relacion(vinculo.alumno)
        profesores = Profesor.objects.filter(pk__in=ids).select_related('user', 'especialidad')
        nuevos += [{'vinculo': vinculo, 'profesor': p} for p in profesores if (vinculo.alumno_id, p.pk) not in hablados]
    return {'bandeja': conversaciones, 'bandeja_activa': activa, 'bandeja_mensajes': mensajes,
            'bandeja_nuevos': nuevos}
