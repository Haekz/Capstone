"""Marco de las paginas que comparten varios roles (Notificaciones, Ayuda y soporte, Eliminar mi cuenta...).

Cada portal con base propia las muestra dentro de su marco; el apoderado, o quien no tiene un rol activo, sigue en el
diseno publico (su propio portal usa ese diseno). Las plantillas hacen {% extends base %} con lo que devuelve
contexto_de_marco; si una vista no lo pasa, {% extends base|default:'alumnos/base.html' %} las deja como siempre.
"""

from alumnos.roles import ALUMNO, APODERADO, PROFESOR, perfil_de, rol_en_sesion
from alumnos.utils import es_menor

BASE_PUBLICA = 'alumnos/base.html'
BASES_DE_PORTAL = {
    PROFESOR: 'user_profesor/base_docente.html',
    ALUMNO: 'alumnos/base_alumno.html',
}
# El apoderado no esta en BASES_DE_PORTAL a propósito: su marco solo llega a las paginas que ya tienen su diseño en ese
# marco (las demas compartidas -notificaciones, reseñas, perfil del profesor- siguen en el diseño publico, como hasta ahora).
BASE_APODERADO = 'apoderados/base_apoderado.html'
SECCIONES_DEL_APODERADO = ('cuenta', 'registrar', 'vincular', 'mensajes', 'clases', 'ayuda', 'paquetes')


def contexto_apoderado(request, seccion):
    """Marco del portal del apoderado para una pagina de ``seccion``. Vacio si quien mira no es apoderado o la
    seccion aun no tiene su diseño en ese marco. La barra lateral usa ``apoderado`` y ``vinculos``."""
    if rol_en_sesion(request) != APODERADO or seccion not in SECCIONES_DEL_APODERADO:
        return {}
    apoderado = perfil_de(request.user, APODERADO)
    return {'base': BASE_APODERADO, 'en_portal': True, 'seccion_menu': seccion, 'titulo_en_barra': True,
            'apoderado': apoderado, 'vinculos': apoderado.vinculos.select_related('alumno__user')}


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
    contexto.update(contexto_apoderado(request, seccion))
    return contexto
