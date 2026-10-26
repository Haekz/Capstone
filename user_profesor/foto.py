"""Foto de perfil del profesor: validarla y guardarla.

La foto la ven los alumnos en el perfil profesional, por eso:
- Se vuelve a codificar con Pillow: quita los metadatos EXIF (las fotos de
  celular traen la ubicacion GPS) y descarta archivos disfrazados de imagen.
- Se sirve por la vista foto_profesor con la misma regla que el perfil
  publico. MEDIA_URL sigue sin publicarse: ahi tambien viven los titulos.
"""

import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

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


def guardar(user, jpeg):
    """Reemplaza la foto del usuario (no guarda el modelo). Nombre al azar: no revela de quien es."""
    if user.foto_perfil:
        user.foto_perfil.delete(save=False)
    user.foto_perfil.save(f'{uuid.uuid4().hex}.jpg', ContentFile(jpeg), save=False)
