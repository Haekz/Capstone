"""Reglas de permiso del modulo que tambien usan otras apps (alumnos)."""

from alumnos.roles import APODERADO

from .models import Apoderado, Vinculo


def vinculo_contratable(request, id_vinculo):
    """Vinculo con el que el apoderado en sesion puede contratar, o None.

    Exige apoderado con identidad verificada y vinculo propio verificado con el
    certificado de nacimiento: un id ajeno o manipulado da None.
    """
    apoderado_id = request.session.get(APODERADO.clave_sesion)
    if not apoderado_id or not str(id_vinculo or '').isdigit():
        return None
    return (Vinculo.objects.select_related('apoderado', 'alumno__user')
            .filter(pk=id_vinculo, apoderado_id=apoderado_id, estado=Vinculo.VERIFICADO,
                    apoderado__estado=Apoderado.VERIFICADO)
            .first())


def clase_pagada_por_apoderado(inscripcion):
    """Menores en la sala virtual: solo clases de un paquete que pago un apoderado
    cuyo vinculo con el estudiante sigue autorizado (si se revoca, deja de entrar)."""
    compra = getattr(inscripcion.paquete, 'compra_apoderado', None) if inscripcion.paquete_id else None
    return bool(compra and compra.vinculo and compra.vinculo.autoriza(inscripcion.alumno))
