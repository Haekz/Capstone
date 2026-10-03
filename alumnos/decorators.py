"""Decoradores de control de acceso basados en la sesion del proyecto.

No se usa @login_required porque la autenticacion no vive en request.user
sino en claves de sesion propias: 'alumno_id', 'profesor_id' o 'admin_id'.
"""

from functools import wraps

from django.http import JsonResponse
from django.shortcuts import redirect


def _sesion_requerida(clave, denegar):
    """Construye un decorador que exige ``clave`` en la sesion.

    ``denegar`` es un callable (no una respuesta ya construida) porque
    ``redirect()`` debe resolverse en la peticion, no al importar el modulo.
    """

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.session.get(clave):
                return denegar(request)
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


def _sesion_invalida_json(_request):
    return JsonResponse({"success": False, "message": "Sesión inválida."})


# Sin sesion de admin se va al login.
admin_required = _sesion_requerida("admin_id", lambda _r: redirect("login"))

# Sin sesion de profesor se va al registro de profesor.
profesor_required = _sesion_requerida(
    "profesor_id", lambda _r: redirect("regis_prof")
)

# Para endpoints JSON: un redirect romperia al cliente que espera 'success'.
profesor_required_json = _sesion_requerida(
    "profesor_id", _sesion_invalida_json
)

admin_required_json = _sesion_requerida(
    "admin_id", _sesion_invalida_json
)
