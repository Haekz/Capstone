"""Reglas de permiso del modulo que tambien usan otras apps (alumnos)."""

from alumnos.roles import APODERADO
from alumnos.utils import es_menor

from .models import ClaveDelApoderado, Vinculo


def vinculo_contratable(request, id_vinculo):
    """Vinculo con el que el apoderado en sesion puede actuar por el estudiante, o None.

    Vinculo propio que autoriza (Vinculo.autoriza: verificado, apoderado
    verificado y estudiante aun menor): un id ajeno o manipulado da None.
    """
    apoderado_id = request.session.get(APODERADO.clave_sesion)
    if not apoderado_id or not str(id_vinculo or '').isdigit():
        return None
    vinculo = (Vinculo.objects.select_related('apoderado', 'alumno__user')
               .filter(pk=id_vinculo, apoderado_id=apoderado_id).first())
    return vinculo if vinculo and vinculo.autoriza(vinculo.alumno) else None


def debe_renovar_clave(user):
    """Fase 1d: adulto que sigue con la contrasena que definio su apoderado."""
    return not es_menor(user) and ClaveDelApoderado.objects.filter(user=user).exists()


def clase_pagada_por_apoderado(inscripcion):
    """Menores en la sala virtual: solo clases de un paquete que pago un apoderado
    cuyo vinculo con el estudiante sigue autorizado (si se revoca, deja de entrar)."""
    compra = getattr(inscripcion.paquete, 'compra_apoderado', None) if inscripcion.paquete_id else None
    return bool(compra and compra.vinculo and compra.vinculo.autoriza(inscripcion.alumno))
