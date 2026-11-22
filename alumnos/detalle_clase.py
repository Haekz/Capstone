"""Pagina de una clase reservada (21-nov): lo que abre el boton de los correos de reserva.

La ven el alumno, su apoderado y el profesor de la clase, cada uno con lo suyo. Es de solo lectura: no hay ninguna ruta
nueva que cambie datos. Para cambiar el horario envia a la pantalla de cada rol, que ya tiene su flujo y su regla
(4 h el alumno y el apoderado, 12 h el profesor). Quien no tiene relacion con la clase recibe 404, como si no existiera.
Privacidad: nombre y apellido del otro (del menor, el profesor ve solo el nombre de pila) y nada mas: ni RUT, ni correo,
ni telefono; el profesor no ve al apoderado.
"""

from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from agenda import cancelacion
from apoderados.models import Vinculo
from apoderados.permisos import clase_pagada_por_apoderado

from .models import Inscripcion
from .roles import ALUMNO, APODERADO, PROFESOR
from .sala_virtual import es_profesor_habilitado_de
from .utils import es_menor, nombre_para_el_profesor

CAMBIO_A_TIEMPO = 'Puedes cambiar el horario o cancelar sin costo hasta 4 horas antes de la clase.'
CAMBIO_TARDE = ('Faltan menos de 4 horas: ya no se puede cambiar el horario. Si cancelas, la clase se descuenta '
                'del paquete y el profesor la cobra.')
CAMBIO_MENOR = 'Tu apoderado puede cambiar el horario o cancelar la clase.'
CAMBIO_PROFESOR = ('Si no puedes dar la clase, cancélala hasta 12 horas antes: avisamos al alumno para que reagende, '
                   'la clase vuelve a su paquete y esa hora queda cerrada en tu agenda.')
CAMBIO_PROFESOR_TARDE = ('Faltan menos de 12 horas: ya no puedes cancelar desde la plataforma. '
                         'Conversa con el alumno o su apoderado.')


def _rol_y_vinculo(user, inscripcion):
    """(rol, vinculo) de quien mira la clase: el profesor titular, el alumno o un apoderado que hoy autoriza."""
    if inscripcion.clase.profesor.user_id == user.id:
        return PROFESOR.clave, None
    if inscripcion.alumno.user_id == user.id:
        return ALUMNO.clave, None
    vinculos = Vinculo.objects.filter(alumno=inscripcion.alumno, apoderado__user=user).select_related('apoderado')
    vinculo = next((v for v in vinculos if v.autoriza(inscripcion.alumno)), None)
    if vinculo is None:
        raise Http404  # sin relacion con la clase: no se revela que existe
    return APODERADO.clave, vinculo


def _puede_entrar(rol, user, inscripcion):
    """Mismas reglas que la sala virtual. El apoderado no entra: lo hace el estudiante desde su cuenta (SCRUM-87)."""
    if not inscripcion.puede_unirse:
        return False
    if rol == PROFESOR.clave:
        return es_profesor_habilitado_de(inscripcion.clase, user)
    return rol == ALUMNO.clave and (not es_menor(user) or clase_pagada_por_apoderado(inscripcion))


def _cambio(rol, inscripcion, vinculo):
    """(texto, url, boton) para cambiar el horario, o None si ya no se puede tocar (empezo o no esta activa).

    Sin url ni boton cuando la persona no puede actuar (menor, o profesor con menos de 12 h).
    """
    if not inscripcion.puede_cancelar:
        return None
    if rol == PROFESOR.clave:
        if cancelacion.a_tiempo(inscripcion.sesion):
            return CAMBIO_PROFESOR, reverse('panel_profesor'), 'Ir a mi agenda'
        return CAMBIO_PROFESOR_TARDE, None, None
    if rol == ALUMNO.clave and es_menor(inscripcion.alumno.user):
        return CAMBIO_MENOR, None, None
    url = reverse('apoderado_clases_estudiante', args=[vinculo.pk]) if vinculo else reverse('alumno_pag1')
    if inscripcion.a_tiempo_para_cambiar:
        return CAMBIO_A_TIEMPO, url, 'Cambiar el horario'
    return CAMBIO_TARDE, url, 'Cancelar la clase'


@never_cache
def detalle_clase(request, pk):
    user = request.user
    if not (user.is_authenticated and user.is_active):  # entra y vuelve aqui: el login lee `next`
        return redirect(f"{reverse('login')}?{urlencode({'next': request.get_full_path()})}")
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related('alumno__user', 'clase__asignatura', 'clase__profesor__user', 'sesion',
                                           'paquete'), pk=pk, sesion__isnull=False)
    rol, vinculo = _rol_y_vinculo(user, inscripcion)
    es_profesor = rol == PROFESOR.clave
    otro = nombre_para_el_profesor(inscripcion.alumno.user) if es_profesor else inscripcion.clase.profesor.nombre
    return render(request, 'alumnos/detalle_clase.html', {
        'inscripcion': inscripcion,
        'rol': rol,
        'rotulo_otro': 'Alumno' if es_profesor else 'Profesional',
        'otro': otro,
        'estudiante': inscripcion.alumno.user.get_full_name() if rol == APODERADO.clave else '',
        'puede_entrar': _puede_entrar(rol, user, inscripcion),
        'cambio': _cambio(rol, inscripcion, vinculo),
    })
