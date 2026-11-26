"""Archivos de video en Cloudflare R2 (API compatible con S3). La ficha de cada video es la tabla Video (videoteca.py).

El alumno no descarga desde la web: tras revisar su acceso, la web lo redirige a un enlace firmado que vence
(enlace()) y R2 entrega el archivo, con Range para adelantar y retroceder. Asi el video no pasa por el servidor.

Sin las cuatro variables R2_* los videos quedan desactivados: _s3() lanza AlmacenNoConfigurado. Un solo cliente por
proceso, creado al primer uso (seguro con los workers de Gunicorn).
Regla: las claves nunca se escriben en logs, excepciones ni respuestas.
"""

import threading

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

# Un video dura hasta 30 minutos: el enlace alcanza para verlo entero con pausas. Si vence igual, el reproductor
# pide otro a la web (videos_apoyo.html) y sigue desde el mismo segundo.
DURACION_ENLACE_SEG = 2 * 60 * 60

_cliente = None
_candado = threading.Lock()


class AlmacenNoConfigurado(Exception):
    """Faltan variables R2_*: los videos estan desactivados."""


ERRORES = (AlmacenNoConfigurado, BotoCoreError, ClientError)  # "R2 no esta disponible": lo que hay que atrapar


def _s3():
    global _cliente
    if _cliente is None:
        with _candado:
            if _cliente is None:
                if not settings.R2_CONFIGURADO:
                    raise AlmacenNoConfigurado('Faltan las variables R2_*.')
                _cliente = boto3.client(
                    's3',
                    endpoint_url=settings.R2_ENDPOINT,
                    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                    region_name='auto',  # R2 no tiene regiones; 'auto' es lo que pide Cloudflare
                    config=Config(signature_version='s3v4', retries={'max_attempts': 3, 'mode': 'standard'}),
                )
    return _cliente


def usar_cliente(cliente):
    """Inyecta un cliente (un R2 de mentira) en pruebas."""
    global _cliente
    with _candado:
        _cliente = cliente


def restablecer():
    """Vuelve al estado inicial: el proximo uso crea un cliente nuevo con los settings de ese momento."""
    usar_cliente(None)


def exigir_configurado():
    """AlmacenNoConfigurado si faltan las variables R2_*. No consulta a R2: solo arma el cliente."""
    _s3()


def _clave(video_id):
    return f'videos/{video_id}.mp4'


def guardar(video_id, archivo):
    """Sube el archivo (desde donde este su posicion actual)."""
    _s3().upload_fileobj(archivo, settings.R2_BUCKET, _clave(video_id), ExtraArgs={'ContentType': 'video/mp4'})


def enlace(video_id):
    """Enlace firmado para ver el video; vence en DURACION_ENLACE_SEG. Se firma aqui mismo: no consulta a R2."""
    return _s3().generate_presigned_url('get_object', Params={'Bucket': settings.R2_BUCKET, 'Key': _clave(video_id)},
                                        ExpiresIn=DURACION_ENLACE_SEG)


def borrar(video_id):
    _s3().delete_object(Bucket=settings.R2_BUCKET, Key=_clave(video_id))
