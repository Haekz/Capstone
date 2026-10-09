"""Titulo profesional del profesor: subirlo, validarlo y revisarlo.

Regla: sin titulo APROBADO por un admin el profesor no puede hacer clases
(no se le asignan, no aparece para los alumnos y no se puede inscribir
nadie en sus clases).
"""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from alumnos.models import Profesor

EXTENSIONES = {'.pdf', '.jpg', '.jpeg', '.png'}
# Primeros bytes de cada formato: la extension sola se falsifica facil.
FIRMAS = (b'%PDF', b'\xff\xd8\xff', b'\x89PNG')


def validar_archivo(archivo):
    if archivo is None:
        raise ValidationError('Selecciona el archivo de tu título.')
    if Path(archivo.name).suffix.lower() not in EXTENSIONES:
        raise ValidationError('Formato no permitido. Sube un PDF, JPG o PNG.')
    if archivo.size > settings.TITULO_MAX_MB * 1024 * 1024:
        raise ValidationError(f'El archivo supera los {settings.TITULO_MAX_MB} MB.')
    cabecera = archivo.read(8)
    archivo.seek(0)
    if not cabecera.startswith(FIRMAS):
        raise ValidationError('El archivo no parece un PDF o imagen válido.')


def subir(profesor, archivo):
    """Guarda el titulo y lo deja en revision. Lanza ValidationError."""
    if not profesor.puede_subir_titulo:
        raise ValidationError('Tu título ya está en revisión o aprobado.')
    validar_archivo(archivo)
    if profesor.titulo_archivo:
        profesor.titulo_archivo.delete(save=False)
    extension = Path(archivo.name).suffix.lower()
    profesor.titulo_archivo.save(f'profesor_{profesor.id_profesor}{extension}', archivo, save=False)
    profesor.titulo_estado = Profesor.TITULO_EN_REVISION
    profesor.titulo_observacion = ''
    profesor.titulo_actualizado = timezone.now()
    profesor.save()


def resolver(profesor, aprobar, observacion=''):
    """Decision del admin sobre un titulo en revision."""
    if profesor.titulo_estado != Profesor.TITULO_EN_REVISION:
        raise ValidationError('Ese título no está pendiente de revisión.')
    if not aprobar and not observacion.strip():
        raise ValidationError('Indica el motivo del rechazo.')
    profesor.titulo_estado = Profesor.TITULO_APROBADO if aprobar else Profesor.TITULO_RECHAZADO
    profesor.titulo_observacion = '' if aprobar else observacion.strip()[:200]
    profesor.titulo_actualizado = timezone.now()
    profesor.save()
