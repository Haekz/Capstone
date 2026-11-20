"""Comprador de prueba que ya acepto Terminos y Privacidad (alumnos/aceptacion.py).

Las pruebas de compra no son sobre la aceptacion: con esto no la repiten. Las de la aceptacion (test_aceptacion.py)
parten de alguien que todavia no acepto.
"""

from alumnos.aceptacion import VERSION
from alumnos.models import AceptacionLegal


def aceptar_terminos(user):
    AceptacionLegal.objects.get_or_create(user=user, version=VERSION)
    return user
