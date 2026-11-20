"""Registro de supresiones: volver a eliminar a quien ya se elimino si se restaura un respaldo (respuesta legal, E4).

Un respaldo restaurado trae de vuelta cuentas que ya se eliminaron. Para no reponerlas en servicio:

1. ``eliminar`` es el unico camino para eliminar una cuenta (solicitud del usuario o admin): anota una huella del RUT
   y del correo y luego aplica ``mensajes.supresion.suprimir_cuenta``.
2. ``exportar`` saca el registro a un archivo. Ese archivo debe guardarse FUERA de la base de datos: restaurar un
   respaldo de la base devuelve tambien el registro a como estaba, y perderia justo las supresiones posteriores.
3. Tras restaurar, y antes de reabrir el servicio, ``reaplicar`` importa el archivo y elimina de nuevo las cuentas que
   coinciden. Solo las creadas antes de la supresion: quien se registro de nuevo despues no se toca.

Las huellas son HMAC-SHA256 con una clave secreta (settings.SUPRESIONES_CLAVE). Un hash sin clave de un RUT se
adivina probando los pocos RUT posibles; con la clave fuera de la base, el registro no revela a nadie. Si la clave
cambia, el registro deja de reconocer a las personas ya eliminadas.
"""

import hashlib
import hmac
from datetime import datetime

from django.conf import settings
from django.db import transaction

from alumnos.backends import normalizar_rut_canonico
from alumnos.models import CustomUser
from mensajes.supresion import suprimir_cuenta

from .models import RegistroSupresion

LARGO_HUELLA = 64  # hex de SHA-256


def _clave():
    return (settings.SUPRESIONES_CLAVE or f'supresiones:{settings.SECRET_KEY}').encode()


def huella(valor):
    """Huella de un RUT o un correo, sin importar como venga escrito (con o sin puntos, mayusculas). '' si no hay."""
    normal = normalizar_rut_canonico(valor)
    return hmac.new(_clave(), normal.encode(), hashlib.sha256).hexdigest() if normal else ''


def eliminar(user):
    """Elimina la cuenta (borrada o seudonimizada, segun mensajes.supresion) y deja su huella en el registro.
    Devuelve True si se borro por completo."""
    with transaction.atomic():
        huellas = {'huella_rut': huella(user.rut), 'huella_correo': huella(user.email)}  # despues ya no existen
        if any(huellas.values()):
            RegistroSupresion.objects.create(**huellas)
        return suprimir_cuenta(user)


def exportar():
    """El registro como lista de filas simples, para guardarla fuera de la base."""
    return [{'rut': r.huella_rut, 'correo': r.huella_correo, 'fecha': r.fecha.isoformat()}
            for r in RegistroSupresion.objects.all()]


def _fila_valida(fila):
    try:
        huellas = (fila['rut'], fila['correo'])
        datetime.fromisoformat(fila['fecha'])
    except (KeyError, TypeError, ValueError):
        return False
    return all(isinstance(h, str) and len(h) in (0, LARGO_HUELLA) for h in huellas)


def importar(filas):
    """Suma al registro las filas que aun no estan (sin duplicar). ValueError si el archivo no tiene el formato."""
    filas = list(filas)
    if not all(_fila_valida(f) for f in filas):
        raise ValueError('El archivo no tiene el formato del registro de supresiones.')
    existentes = set(RegistroSupresion.objects.values_list('huella_rut', 'huella_correo', 'fecha'))
    nuevas = {}
    for fila in filas:
        fecha = datetime.fromisoformat(fila['fecha'])
        clave = (fila['rut'], fila['correo'], fecha)
        if clave not in existentes:
            nuevas[clave] = RegistroSupresion(huella_rut=clave[0], huella_correo=clave[1], fecha=fecha)
    RegistroSupresion.objects.bulk_create(nuevas.values())
    return len(nuevas)


def _ultima_supresion_por_huella():
    ultima = {}
    for h_rut, h_correo, fecha in RegistroSupresion.objects.values_list('huella_rut', 'huella_correo', 'fecha'):
        for h in (h_rut, h_correo):
            if h:
                ultima[h] = max(fecha, ultima.get(h, fecha))
    return ultima


def reaplicar(simular=False):
    """Vuelve a eliminar las cuentas vigentes que coinciden con el registro y se crearon antes de esa supresion.
    Devuelve cuantas. Con ``simular`` solo las cuenta."""
    ultima = _ultima_supresion_por_huella()
    pks = []
    # Primero se reunen los ids: eliminar mientras se recorre la consulta la dejaria inconsistente.
    for user in CustomUser.objects.filter(suprimida__isnull=True).only('pk', 'rut', 'email', 'date_joined').iterator():
        fechas = [ultima[h] for h in (huella(user.rut), huella(user.email)) if h in ultima]
        if fechas and user.date_joined < max(fechas):
            pks.append(user.pk)
    if not simular:
        for pk in pks:
            suprimir_cuenta(CustomUser.objects.get(pk=pk))
    return len(pks)
