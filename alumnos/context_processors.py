"""Estado de sesion para el menu global.

Expone `usuario_sesion` a todas las plantillas para que el menu sepa quien
esta conectado sin que cada vista tenga que calcularlo.

Fuente de la verdad: `request.user.is_authenticated`. Las claves de sesion
por rol ('alumno_id', 'profesor_id', 'admin_id') deciden QUE rol mostrar,
no SI hay sesion.
"""

from django.urls import reverse

# El orden replica la precedencia de `custom_login()`, para que el menu y el
# login no discrepen si un usuario tuviera mas de un perfil.
_ROLES = (
    {
        'perfil': 'perfil_alumno',
        'clave_sesion': 'alumno_id',
        'etiqueta': 'Alumno',
        'texto_panel': 'Mi portal',
        'ruta_panel': 'alumno_pag1',
        'ruta_logout': 'logout_alumno',
    },
    {
        'perfil': 'perfil_profesor',
        'clave_sesion': 'profesor_id',
        'etiqueta': 'Profesor',
        'texto_panel': 'Mi panel',
        'ruta_panel': 'panel_profesor',
        'ruta_logout': 'logout_prof',
    },
    {
        'perfil': 'perfil_tutor',
        'clave_sesion': 'admin_id',
        'etiqueta': 'Administrador',
        'texto_panel': 'Panel admin',
        'ruta_panel': 'dashboard_admin',
        'ruta_logout': 'logout_admin',
    },
)

_ROL_ADMIN = _ROLES[2]

_ANONIMO = {'autenticado': False}


def _nombre_visible(user, perfil):
    """Nombre para saludar: el del perfil, o lo que tenga el User."""
    nombre_perfil = getattr(perfil, 'nombre', '') if perfil else ''
    return nombre_perfil or user.first_name or user.username


def _rol_activo(user, sesion):
    """Devuelve (rol, perfil) para el usuario, o (None, None).

    El getattr es seguro: el descriptor de una OneToOne inversa lanza
    RelatedObjectDoesNotExist, que hereda de AttributeError.
    """
    for rol in _ROLES:
        perfil = getattr(user, rol['perfil'], None)
        if perfil is not None or sesion.get(rol['clave_sesion']):
            return rol, perfil

    # Staff y superusuarios entran al portal admin sin tener un Tutor asociado.
    if user.is_staff or user.is_superuser:
        return _ROL_ADMIN, None

    return None, None


def estado_sesion(request):
    """Expone `usuario_sesion` a todas las plantillas.

    Una sola clave con forma de diccionario para no pisar variables de
    contexto de las vistas.
    """
    user = getattr(request, 'user', None)

    if user is None or not user.is_authenticated:
        return {'usuario_sesion': _ANONIMO}

    rol, perfil = _rol_activo(user, request.session)

    if rol is None:
        # Autenticado pero sin perfil: se le ofrece cerrar sesion, no un panel.
        return {
            'usuario_sesion': {
                'autenticado': True,
                'nombre': _nombre_visible(user, None),
                'rol': '',
                'texto_panel': '',
                'url_panel': '',
                'url_logout': reverse('logout_alumno'),
            }
        }

    return {
        'usuario_sesion': {
            'autenticado': True,
            'nombre': _nombre_visible(user, perfil),
            'rol': rol['etiqueta'],
            'texto_panel': rol['texto_panel'],
            'url_panel': reverse(rol['ruta_panel']),
            'url_logout': reverse(rol['ruta_logout']),
        }
    }
