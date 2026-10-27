"""Decoradores de control de acceso por rol.

No se usa @login_required porque el rol activo vive en claves de sesion
propias ('alumno_id', 'profesor_id', 'admin_id'); ver alumnos/roles.py.

Regla comun a los tres portales:
- Con la sesion del rol correcto -> entra.
- Con sesion de OTRO rol -> vuelve a su propio portal (nunca ve uno ajeno).
- Anonimo -> ``anonimo(request)`` (login, registro o JSON segun el caso).
"""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect

from apoderados.permisos import debe_renovar_clave

from .roles import ADMIN, ALUMNO, APODERADO, PROFESOR, redirigir_a_portal, rol_en_sesion


def _rol_requerido(rol, anonimo, json=False):
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if request.session.get(rol.clave_sesion):
                user = getattr(request, 'user', None)
                if user is not None and (not user.is_authenticated or not user.is_active):
                    from django.contrib.auth import logout
                    logout(request)
                    return anonimo(request)
                return vista(request, *args, **kwargs)

            otro = rol_en_sesion(request)
            if otro is not None and not json:
                return redirigir_a_portal(otro)

            return anonimo(request)

        return envoltura

    return decorador


def _al_login(_request):
    return redirect('login')


def _sesion_invalida_json(_request):
    return JsonResponse({"success": False, "message": "Sesión inválida."})


admin_required = _rol_requerido(ADMIN, _al_login)
apoderado_required = _rol_requerido(APODERADO, _al_login)

# Solo el rol, sin la regla de abajo: para la pantalla donde se cumple esa regla.
alumno_sesion_required = _rol_requerido(ALUMNO, _al_login)


def alumno_required(vista):
    """Rol alumno y, al cumplir 18, contrasena propia (fase 1d de menores):
    si sigue con la que definio su apoderado, primero define una nueva."""
    @wraps(vista)
    def con_clave_propia(request, *args, **kwargs):
        if debe_renovar_clave(request.user):
            return redirect('nueva_clave_estudiante')
        return vista(request, *args, **kwargs)

    return alumno_sesion_required(con_clave_propia)

# El profesor anonimo va a su registro, que tambien trae el login de profesor.
profesor_required = _rol_requerido(PROFESOR, lambda _r: redirect('regis_prof'))

# Para endpoints JSON: un redirect romperia al cliente que espera 'success'.
profesor_required_json = _rol_requerido(
    PROFESOR, _sesion_invalida_json, json=True
)

admin_required_json = _rol_requerido(
    ADMIN, _sesion_invalida_json, json=True
)
