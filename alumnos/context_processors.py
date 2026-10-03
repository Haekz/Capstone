"""Estado de sesion para el menu global.

El menu vive en `alumnos/templates/alumnos/base.html`, que heredan 12
templates de tres apps distintas. Muchas de las vistas que lo renderizan
pasan un `context = {}` vacio, asi que el template no tiene forma de saber
quien esta al otro lado.

Calcular el estado en cada vista seria repetir la misma logica una y otra
vez (y olvidarla en la siguiente vista que alguien agregue). Un context
processor lo resuelve en un solo lugar para todas las respuestas.

Fuente de la verdad: `request.user.is_authenticated` para SABER si hay
sesion, y `alumnos.roles` para decidir QUE rol mostrar. Asi el menu, el
login y los decoradores nunca discrepan sobre el rol de un usuario.
"""

from django.urls import reverse

from .roles import ROLES, perfil_de, rol_en_sesion

_ANONIMO = {'autenticado': False}


def _nombre_visible(user, perfil):
    """Nombre para saludar: el del perfil, o lo que tenga el User."""
    nombre_perfil = getattr(perfil, 'nombre', '') if perfil else ''
    return nombre_perfil or user.first_name or user.username


def _iniciales(nombre):
    """Hasta dos iniciales para el circulo del menu de cuenta.

    'Alumno Prueba' -> 'AP'; 'Dani' -> 'D'; un RUT como '11111111-1' -> '1'.
    """
    palabras = [p for p in nombre.split() if p[:1].isalnum()]
    return ''.join(p[0] for p in palabras[:2]).upper() or '?'


def _datos_cuenta(nombre, **extra):
    """Arma el diccionario de sesion; un solo lugar para las claves comunes."""
    return {
        'usuario_sesion': {
            'autenticado': True,
            'nombre': nombre,
            'iniciales': _iniciales(nombre),
            'url_cambiar_clave': reverse('password_change'),
            **extra,
        }
    }


def _rol_activo(user, request):
    """Devuelve (rol, perfil) para el menu, o (None, None).

    Manda el rol con sesion abierta; si no hay ninguno, el del perfil. Un
    staff sin perfil NO recibe panel: el portal admin exige un Tutor.
    """
    rol = rol_en_sesion(request)
    if rol is not None:
        return rol, perfil_de(user, rol)

    for rol in ROLES:
        perfil = perfil_de(user, rol)
        if perfil is not None:
            return rol, perfil

    return None, None


def estado_sesion(request):
    """Expone `usuario_sesion` a todas las plantillas.

    Se usa una sola clave con forma de diccionario (en vez de varias
    sueltas) para no pisar variables de contexto de las vistas.
    """
    user = getattr(request, 'user', None)

    if user is None or not user.is_authenticated:
        return {'usuario_sesion': _ANONIMO}

    rol, perfil = _rol_activo(user, request)

    if rol is None:
        # Autenticado pero sin perfil en el sistema. Se le ofrece cerrar
        # sesion, no un panel al que no tiene acceso.
        return _datos_cuenta(
            _nombre_visible(user, None),
            rol='',
            texto_panel='',
            url_panel='',
            url_logout=reverse('logout_alumno'),
        )

    return _datos_cuenta(
        _nombre_visible(user, perfil),
        rol=rol.etiqueta,
        texto_panel=rol.texto_panel,
        url_panel=reverse(rol.ruta_portal),
        url_logout=reverse(rol.ruta_logout),
    )
