"""Unica fuente de verdad para los roles del sistema.

Antes la regla "que rol tiene este usuario" estaba copiada en cuatro
lugares (custom_login, login_prof, login_admin y el context processor) y
cada copia decidia distinto. Ademas miraba el campo ``CustomUser.rol``,
cuyo valor por defecto es 'alumno': un superusuario o un tutor creado sin
``rol`` explicito terminaba en el portal de alumno con ``alumno_id =
user.id``, un numero que no es un id de alumno.

Regla actual: el rol lo define el PERFIL asociado (Alumno, Profesor o
Tutor), porque la sesion guarda el id de ese perfil. Sin perfil no hay
portal. El orden de ROLES es la precedencia si alguien tuviera dos.
"""

from dataclasses import dataclass

from django.shortcuts import redirect


@dataclass(frozen=True)
class Rol:
    clave: str          # identificador interno: 'alumno', 'profesor', 'admin'
    perfil: str         # related_name del OneToOne en CustomUser
    campo_id: str       # pk del perfil que se guarda en la sesion
    clave_sesion: str   # clave de sesion que marca el rol activo
    ruta_portal: str    # nombre de la URL del portal del rol
    ruta_logout: str
    etiqueta: str
    texto_panel: str


ALUMNO = Rol('alumno', 'perfil_alumno', 'id_alumno', 'alumno_id',
             'alumno_pag1', 'logout_alumno', 'Alumno', 'Mi portal')
PROFESOR = Rol('profesor', 'perfil_profesor', 'id_profesor', 'profesor_id',
               'panel_profesor', 'logout_prof', 'Profesor', 'Mi panel')
ADMIN = Rol('admin', 'perfil_tutor', 'id_tutor', 'admin_id',
            'dashboard_admin', 'logout_admin', 'Administrador', 'Panel admin')

ROLES = (ALUMNO, PROFESOR, ADMIN)


def perfil_de(user, rol):
    """Perfil del usuario para ``rol`` o None.

    getattr con default es seguro: el descriptor de una OneToOne inversa
    lanza RelatedObjectDoesNotExist, que hereda de AttributeError.
    """
    return getattr(user, rol.perfil, None)


def resolver_rol(user):
    """Devuelve (rol, perfil) segun el perfil asociado, o (None, None)."""
    if user is None or not user.is_authenticated:
        return None, None
    for rol in ROLES:
        perfil = perfil_de(user, rol)
        if perfil is not None:
            return rol, perfil
    return None, None


def abrir_sesion_rol(request, rol, perfil):
    """Marca ``rol`` como el unico activo en la sesion.

    Se limpian las demas claves para que nunca convivan dos roles: eso era
    lo que mezclaba portales.
    """
    for otro in ROLES:
        request.session.pop(otro.clave_sesion, None)
    request.session[rol.clave_sesion] = getattr(perfil, rol.campo_id)


def rol_en_sesion(request):
    """Rol activo segun la sesion, o None."""
    for rol in ROLES:
        if request.session.get(rol.clave_sesion):
            return rol
    return None


def redirigir_a_portal(rol):
    return redirect(rol.ruta_portal)
