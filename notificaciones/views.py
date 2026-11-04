from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from alumnos.roles import PROFESOR, rol_en_sesion

MAX_VISIBLES = 50

# Cada portal conserva su marco; el resto (alumno, apoderado) sigue en el diseno publico.
BASE_PUBLICA = 'alumnos/base.html'
BASE_DOCENTE = 'user_profesor/base_docente.html'


@never_cache
@login_required
def mis_notificaciones(request):
    """Las ultimas del usuario. Al abrir la pagina quedan leidas (el contador vuelve a 0)."""
    notificaciones = request.user.notificaciones.all()
    visibles = list(notificaciones[:MAX_VISIBLES])  # se evalua antes de marcarlas: se ven las nuevas
    notificaciones.filter(leida=False).update(leida=True)

    en_portal_docente = rol_en_sesion(request) == PROFESOR
    return render(request, 'notificaciones/lista.html', {
        'notificaciones': visibles,
        'base': BASE_DOCENTE if en_portal_docente else BASE_PUBLICA,
        'en_portal': en_portal_docente,  # el menu del portal ya lleva al panel: no hace falta 'Volver'
    })
