from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from alumnos.roles import ALUMNO, PROFESOR, perfil_de, rol_en_sesion
from alumnos.utils import es_menor

MAX_VISIBLES = 50

# Cada portal conserva su marco; quien no tiene uno con base propia (el apoderado) sigue en el diseno publico.
BASE_PUBLICA = 'alumnos/base.html'
BASES_DE_PORTAL = {
    PROFESOR: 'user_profesor/base_docente.html',
    ALUMNO: 'alumnos/base_alumno.html',
}


@never_cache
@login_required
def mis_notificaciones(request):
    """Las ultimas del usuario. Al abrir la pagina quedan leidas (el contador vuelve a 0)."""
    notificaciones = request.user.notificaciones.all()
    visibles = list(notificaciones[:MAX_VISIBLES])  # se evalua antes de marcarlas: se ven las nuevas
    notificaciones.filter(leida=False).update(leida=True)

    rol = rol_en_sesion(request)
    base = BASES_DE_PORTAL.get(rol)
    contexto = {
        'notificaciones': visibles,
        'base': base or BASE_PUBLICA,
        'en_portal': base is not None,  # el menu del portal ya lleva al panel: no hace falta 'Volver'
    }
    if rol == ALUMNO:
        # El menu y la ficha de base_alumno usan alumno y es_menor; su barra superior ya lleva el titulo de la pagina
        contexto.update(alumno=perfil_de(request.user, ALUMNO), es_menor=es_menor(request.user), titulo_en_barra=True)
    return render(request, 'notificaciones/lista.html', contexto)
