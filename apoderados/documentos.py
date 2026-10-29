"""Documentos por revisar (fase 2a): carnet del apoderado y documento del vinculo.

Se guardan cifrados en la base de datos (PostgreSQL), nunca en disco: Railway borra
el disco en cada deploy. Solo JPG o PNG: al subirlos se vuelven a codificar, asi se
descartan archivos que no son imagenes y se borran sus metadatos (por ejemplo, la
ubicacion GPS de una foto). Al verlos se les pone marca de agua con el nombre de
quien los abre. Se borran al aprobar o rechazar la revision, o a los 30 dias.
"""

import base64
import hashlib
import io

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

TAMANO_MAXIMO = 5 * 1024 * 1024
LADO_MAXIMO = 2000  # pixeles: suficiente para leer un carnet o un certificado
FORMATOS = ('JPEG', 'PNG')
ERROR_FORMATO = 'Sube una foto o imagen en formato JPG o PNG.'


def _cifrador():
    # Sin DOCUMENTOS_CLAVE se deriva de SECRET_KEY. Si la clave cambia, los documentos
    # pendientes dejan de leerse y hay que pedirlos de nuevo (viven 30 dias como maximo).
    clave = settings.DOCUMENTOS_CLAVE or base64.urlsafe_b64encode(
        hashlib.sha256(f'documentos-apoderados:{settings.SECRET_KEY}'.encode()).digest())
    return Fernet(clave)


def preparar(archivo):
    """Valida la imagen subida y la devuelve re-codificada y cifrada: (contenido, formato)."""
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError('El archivo no puede superar los 5 MB.')
    try:
        imagen = Image.open(archivo)
        formato = imagen.format
        imagen.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError(ERROR_FORMATO)
    if formato not in FORMATOS:
        raise ValidationError(ERROR_FORMATO)
    imagen = ImageOps.exif_transpose(imagen)  # respeta la orientacion antes de descartar el EXIF
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    salida = io.BytesIO()
    if formato == 'JPEG':
        imagen.convert('RGB').save(salida, 'JPEG', quality=85)
    else:
        imagen.save(salida, 'PNG')
    return _cifrador().encrypt(salida.getvalue()), formato


def descifrar(contenido):
    return _cifrador().decrypt(bytes(contenido))  # PostgreSQL entrega un memoryview


def con_marca_de_agua(contenido, texto):
    """JPEG del documento con ``texto`` repetido encima: si se filtra, se sabe quien lo abrio."""
    imagen = Image.open(io.BytesIO(descifrar(contenido))).convert('RGBA')
    ancho, alto = imagen.size
    fuente = ImageFont.load_default(size=max(14, ancho // 28))
    capa = Image.new('RGBA', imagen.size, (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    izquierda, arriba, derecha, abajo = dibujo.textbbox((0, 0), texto, font=fuente)
    paso_x, paso_y = derecha - izquierda + 40, (abajo - arriba) * 4
    for fila, y in enumerate(range(0, alto, paso_y)):
        for x in range(-(fila % 2) * paso_x // 2, ancho, paso_x):
            dibujo.text((x, y), texto, font=fuente, fill=(200, 0, 0, 110))
    salida = io.BytesIO()
    Image.alpha_composite(imagen, capa).convert('RGB').save(salida, 'JPEG', quality=85)
    return salida.getvalue()
