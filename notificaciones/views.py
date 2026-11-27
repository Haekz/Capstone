from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from alumnos.portales import contexto_de_marco
from apoderados.permisos import debe_renovar_clave

MAX_VISIBLES = 50


@never_cache
@login_required
def mis_notificaciones(request):
    """Las ultimas del usuario. Al abrir la pagina quedan leidas (el contador vuelve a 0)."""
    if not request.user.is_active:
        from django.contrib.auth import logout
        logout(request)
        return redirect('login')
    if debe_renovar_clave(request.user):
        return redirect('nueva_clave_estudiante')
    notificaciones = request.user.notificaciones.all()
    visibles = list(notificaciones[:MAX_VISIBLES])  # se evalua antes de marcarlas: se ven las nuevas
    ids_visibles = [n.pk for n in visibles]
    if ids_visibles:
        notificaciones.filter(pk__in=ids_visibles, leida=False).update(leida=True)
    return render(request, 'notificaciones/lista.html', {'notificaciones': visibles, **contexto_de_marco(request)})
