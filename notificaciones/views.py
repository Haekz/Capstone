from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from alumnos.portales import contexto_de_marco

MAX_VISIBLES = 50


@never_cache
@login_required
def mis_notificaciones(request):
    """Las ultimas del usuario. Al abrir la pagina quedan leidas (el contador vuelve a 0)."""
    notificaciones = request.user.notificaciones.all()
    visibles = list(notificaciones[:MAX_VISIBLES])  # se evalua antes de marcarlas: se ven las nuevas
    notificaciones.filter(leida=False).update(leida=True)
    return render(request, 'notificaciones/lista.html', {'notificaciones': visibles, **contexto_de_marco(request)})
