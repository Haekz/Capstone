"""Foto de perfil del profesor: validarla, guardarla, leerla y borrarla.

La foto la ven los alumnos en el perfil profesional, por eso:
- Se vuelve a codificar con Pillow: quita los metadatos EXIF (las fotos de
  celular traen la ubicacion GPS) y descarta archivos disfrazados de imagen.
- Se guarda en PostgreSQL (alumnos.FotoPerfil), no en disco, y se sirve por la
  vista foto_profesor con la misma regla que el perfil publico.
"""

from io import BytesIO

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

from alumnos.models import FotoPerfil

MAX_MB = 5
LADO_MAX = 512  # px: el perfil la muestra a 84-120 px
FORMATOS = {'JPEG', 'PNG', 'WEBP'}


def _sobre_blanco(imagen):
    """Aplana la transparencia sobre blanco (convert('RGB') la dejaria negra)."""
    imagen = imagen.convert('RGBA')
    fondo = Image.new('RGB', imagen.size, 'white')
    fondo.paste(imagen, mask=imagen.getchannel('A'))
    return fondo


def procesar(archivo):
    """Valida la foto y la devuelve como JPEG limpio (bytes). Lanza ValidationError."""
    if archivo.size > MAX_MB * 1024 * 1024:
        raise ValidationError(f'La foto supera los {MAX_MB} MB.')
    try:
        imagen = Image.open(archivo)
        if imagen.format not in FORMATOS:
            raise ValidationError('Formato no permitido. Sube una foto JPG, PNG o WEBP.')
        imagen = ImageOps.exif_transpose(imagen)  # respeta la orientacion antes de perder el EXIF
        puede_tener_transparencia = imagen.mode in ('RGBA', 'LA', 'P')
        imagen = _sobre_blanco(imagen) if puede_tener_transparencia else imagen.convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError('El archivo no es una imagen válida.')
    imagen.thumbnail((LADO_MAX, LADO_MAX))
    salida = BytesIO()
    imagen.save(salida, 'JPEG', quality=85)  # sin exif=: no se copia ningun metadato
    return salida.getvalue()


def _olvidar_si_tiene(user):
    user.__dict__.pop('tiene_foto', None)  # CustomUser.tiene_foto es cached_property: que no quede la respuesta vieja


def guardar(user, jpeg):
    """Reemplaza la foto del usuario por el JPEG que devolvio procesar()."""
    FotoPerfil.objects.update_or_create(user=user, defaults={'contenido': jpeg})
    _olvidar_si_tiene(user)


def leer(user_id):
    """Bytes JPEG de la foto, o None si no tiene."""
    contenido = FotoPerfil.objects.filter(user_id=user_id).values_list('contenido', flat=True).first()
    return None if contenido is None else bytes(contenido)  # PostgreSQL entrega un memoryview


def borrar(user):
    FotoPerfil.objects.filter(user=user).delete()
    _olvidar_si_tiene(user)
