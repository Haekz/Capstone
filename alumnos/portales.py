"""Marco de las paginas que comparten varios roles (Notificaciones, Ayuda y soporte, Eliminar mi cuenta...).

Cada portal con base propia las muestra dentro de su marco; el apoderado, o quien no tiene un rol activo, sigue en el
diseno publico (su propio portal usa ese diseno). Las plantillas hacen {% extends base %} con lo que devuelve
contexto_de_marco; si una vista no lo pasa, {% extends base|default:'alumnos/base.html' %} las deja como siempre.
"""

from alumnos.roles import ALUMNO, PROFESOR, perfil_de, rol_en_sesion
from alumnos.utils import es_menor

BASE_PUBLICA = 'alumnos/base.html'
BASES_DE_PORTAL = {
    PROFESOR: 'user_profesor/base_docente.html',
    ALUMNO: 'alumnos/base_alumno.html',
}


def contexto_de_marco(request, seccion=''):
    """'base' y lo que esa base necesita. en_portal: el menu del portal ya lleva al panel, asi que sobra 'Volver'.

    seccion: a que parte del menu pertenece la pagina ('ayuda'...); cada base marca su propio item.
    """
    rol = rol_en_sesion(request)
    base = BASES_DE_PORTAL.get(rol)
    contexto = {'base': base or BASE_PUBLICA, 'en_portal': base is not None, 'seccion_menu': seccion}
    if rol == ALUMNO:
        # La ficha y el menu de base_alumno usan alumno y es_menor; su barra superior lleva el titulo de la pagina
        contexto.update(alumno=perfil_de(request.user, ALUMNO), es_menor=es_menor(request.user), titulo_en_barra=True)
    return contexto
