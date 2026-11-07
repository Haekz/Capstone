"""Titulo profesional del profesor: subirlo, validarlo y revisarlo.

Regla: sin titulo APROBADO por soporte el profesor no puede hacer clases
(no se le asignan, no aparece para los alumnos y no se puede inscribir
nadie en sus clases). Cada titulo en revision es un ticket de soporte.

Paso 9b: se guarda cifrado en la base con el mismo tratamiento que los documentos
de apoderados (JPG o PNG re-codificado, o PDF de hasta 3 paginas; maximo 5 MB),
soporte lo ve como imagen con marca de agua y el original se borra al decidir.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from alumnos.models import Profesor
from apoderados import documentos
from soporte.models import Ticket
from soporte.tickets import abrir_ticket, cerrar_tickets

from . import asignaturas

PASADO, A_RESUBIR, BORRADO = 'pasado', 'a_resubir', 'borrado'
NO_SE_RECUPERO = 'No es un rechazo: no pudimos recuperar el archivo de tu título. Súbelo de nuevo, por favor.'


def _borrar_archivo_antiguo(profesor):
    """Titulos de antes del paso 9b, en disco: no deben quedar."""
    if profesor.titulo_archivo:
        profesor.titulo_archivo.delete(save=False)


def _cerrar_ticket(profesor):
    """Solo el del titulo: el de sus especializaciones sigue su curso."""
    cerrar_tickets(profesor.tickets.filter(categoria=Ticket.TITULOS))


def subir(profesor, archivo):
    """Guarda el titulo cifrado y lo deja en revision. Lanza ValidationError."""
    if not profesor.puede_subir_titulo:
        raise ValidationError('Tu título ya está en revisión o aprobado.')
    if archivo is None:
        raise ValidationError('Selecciona el archivo de tu título.')
    profesor.titulo_contenido, profesor.titulo_formato = documentos.preparar(archivo)
    _borrar_archivo_antiguo(profesor)
    profesor.titulo_estado = Profesor.TITULO_EN_REVISION
    profesor.titulo_observacion = ''
    profesor.titulo_actualizado = timezone.now()
    with transaction.atomic():
        profesor.save()
        abrir_ticket(Ticket.TITULOS, profesor=profesor)


def resolver(profesor, aprobar, observacion='', ids_asignaturas=()):
    """Decision del agente de soporte sobre un titulo en revision. El original se borra (decidido 02-nov).

    Al aprobar, soporte puede asignarle asignaturas del catalogo (opcional) y se crean sus clases.
    Devuelve las clases nuevas.
    """
    if profesor.titulo_estado != Profesor.TITULO_EN_REVISION:
        raise ValidationError('Ese título no está pendiente de revisión.')
    if not aprobar and not observacion.strip():
        raise ValidationError('Indica el motivo del rechazo.')
    elegidas = asignaturas.del_catalogo(ids_asignaturas, obligatoria=False) if aprobar else []
    profesor.titulo_estado = Profesor.TITULO_APROBADO if aprobar else Profesor.TITULO_RECHAZADO
    profesor.titulo_observacion = '' if aprobar else observacion.strip()[:200]
    profesor.titulo_actualizado = timezone.now()
    profesor.titulo_contenido, profesor.titulo_formato = None, ''
    _borrar_archivo_antiguo(profesor)
    with transaction.atomic():
        Profesor.objects.select_for_update().filter(pk=profesor.pk).first()  # a la vez que una especializacion
        profesor.save()
        _cerrar_ticket(profesor)
        return asignaturas.asignar(profesor, elegidas)  # despues de aprobar: sus bloques ya se pueden generar


def pasar_a_base(profesor):
    """Titulo antiguo en disco -> cifrado en la base (manage.py pasar_titulos_a_base). Devuelve que paso.

    En revision: se cifra; si el archivo se perdio (Railway borra el disco) o no es valido, queda
    rechazado con NO_SE_RECUPERO para que lo vuelva a subir. Ya decidido: el original no se guarda.
    """
    resultado = BORRADO
    if profesor.titulo_estado == Profesor.TITULO_EN_REVISION:
        try:
            with profesor.titulo_archivo.open('rb') as archivo:
                profesor.titulo_contenido, profesor.titulo_formato = documentos.preparar(archivo)
            resultado = PASADO
        except (OSError, ValidationError):
            profesor.titulo_estado = Profesor.TITULO_RECHAZADO
            profesor.titulo_observacion = NO_SE_RECUPERO
            profesor.titulo_actualizado = timezone.now()
            resultado = A_RESUBIR
    _borrar_archivo_antiguo(profesor)  # si ya no estaba en el disco, Django no reclama
    with transaction.atomic():
        profesor.save()
        if resultado == A_RESUBIR:
            _cerrar_ticket(profesor)
    return resultado
