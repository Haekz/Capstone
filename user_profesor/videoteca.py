"""Videos de apoyo del profesor (agregado de videos, fase 1).

El archivo vive en Cloudflare R2 (almacen_videos.py) y su ficha (titulo, materia, duracion, dueno) en la coleccion
`videos` de MongoDB, con el mismo _id: un ObjectId, que es el video_id de VideoCompartido y el que nombran los
reclamos de soporte. Sin MONGODB_URI o sin las variables R2_* los videos quedan desactivados (ERRORES).

El profesor sube MP4 de hasta 30 minutos por cada materia que enseña (sus Clase). La duración se lee de la
caja mvhd del propio MP4: no hace falta instalar ffmpeg. La materia se guarda por id: si el admin la renombra, se
ve el nombre nuevo.
"""

import struct
from contextlib import suppress

from bson import ObjectId
from bson.errors import InvalidId
from django.core.exceptions import ValidationError
from django.utils import timezone

from alumnos.models import Asignatura, Clase, PaqueteClases, VideoCompartido
from comunidad import mongo

from . import almacen_videos

COLECCION = 'videos'
ERRORES = mongo.ERRORES + almacen_videos.ERRORES  # "los videos no estan disponibles": lo que hay que atrapar
DURACION_MAX_SEG = 30 * 60
TAMANO_MAX_MB = 500
TITULO_MIN, TITULO_MAX = 3, 100
NO_ES_MP4 = 'El archivo no es un video MP4 válido.'


def _cajas(archivo, fin=None):
    """Cajas MP4 desde la posición actual hasta `fin`: (tipo, inicio del contenido, fin de la caja)."""
    pos = archivo.tell()
    while fin is None or pos + 8 <= fin:
        archivo.seek(pos)
        cabecera = archivo.read(8)
        if len(cabecera) < 8:
            return
        tamano, tipo = struct.unpack('>I4s', cabecera)
        contenido = pos + 8
        if tamano == 1:  # tamaño de 64 bits, en los 8 bytes siguientes
            tamano = struct.unpack('>Q', archivo.read(8))[0]
            contenido += 8
        if tamano == 0:  # la caja llega hasta el final del archivo
            yield tipo, contenido, fin
            return
        if tamano < contenido - pos:
            raise ValidationError(NO_ES_MP4)
        yield tipo, contenido, pos + tamano
        pos += tamano


def duracion_mp4(archivo):
    """Segundos que dura un MP4. ValidationError si no lo es."""
    try:
        archivo.seek(0)
        cajas = _cajas(archivo)
        if next(cajas, (None,))[0] != b'ftyp':
            raise ValidationError(NO_ES_MP4)
        for tipo, inicio, fin in cajas:
            if tipo != b'moov':
                continue
            archivo.seek(inicio)
            for interior, inicio_mvhd, _ in _cajas(archivo, fin):
                if interior == b'mvhd':
                    archivo.seek(inicio_mvhd)
                    if archivo.read(4)[:1] == b'\x01':  # version 1: fechas y duracion de 64 bits
                        archivo.seek(16, 1)
                        escala, duracion = struct.unpack('>IQ', archivo.read(12))
                    else:
                        archivo.seek(8, 1)
                        escala, duracion = struct.unpack('>II', archivo.read(8))
                    if escala:
                        return duracion / escala
    except struct.error:
        pass
    raise ValidationError(NO_ES_MP4)


def _fichas():
    return mongo.get_db()[COLECCION]


def materias(profesor_id):
    """Las materias que enseña: las de sus clases, sin repetir."""
    return list(Asignatura.objects.filter(clase__profesor_id=profesor_id).distinct().order_by('nombre').values('id', 'nombre'))


def subir(profesor_id, asignatura, titulo, archivo):
    """Guarda el video y devuelve su id. ValidationError con el motivo si no cumple las reglas."""
    titulo = (titulo or '').strip()
    if not TITULO_MIN <= len(titulo) <= TITULO_MAX:
        raise ValidationError(f'El título debe tener entre {TITULO_MIN} y {TITULO_MAX} caracteres.')
    asignatura = str(asignatura or '')
    if not asignatura.isdigit() or not Clase.objects.filter(profesor_id=profesor_id, asignatura_id=asignatura).exists():
        raise ValidationError('Solo puedes subir videos de las materias que enseñas.')
    if not archivo:
        raise ValidationError('Elige un archivo de video MP4.')
    if archivo.size > TAMANO_MAX_MB * 1024 * 1024:
        raise ValidationError(f'El video pesa más de {TAMANO_MAX_MB} MB.')
    duracion = duracion_mp4(archivo)
    if duracion > DURACION_MAX_SEG:
        raise ValidationError(f'El video dura más de {DURACION_MAX_SEG // 60} minutos.')
    archivo.seek(0)
    oid = ObjectId()
    almacen_videos.guardar(str(oid), archivo)
    metadata = {'profesor_id': profesor_id, 'asignatura_id': int(asignatura), 'titulo': titulo, 'duracion_seg': round(duracion)}
    try:
        _fichas().insert_one({'_id': oid, 'filename': archivo.name, 'length': archivo.size,
                              'uploadDate': timezone.now(), 'metadata': metadata})
    except mongo.ERRORES:
        with suppress(*almacen_videos.ERRORES):  # sin ficha nadie lo veria: no dejar el archivo huerfano en R2
            almacen_videos.borrar(str(oid))
        raise
    return str(oid)


def _presentar(docs):
    """Fichas convertidas a lo que se muestra: id, titulo, materia, duracion y fecha."""
    nombres = dict(Asignatura.objects.filter(id__in={d['metadata']['asignatura_id'] for d in docs}).values_list('id', 'nombre'))
    return [{
        'id': str(d['_id']),
        'titulo': d['metadata']['titulo'],
        'asignatura': nombres.get(d['metadata']['asignatura_id'], 'Materia eliminada'),
        'duracion': '{}:{:02d}'.format(*divmod(d['metadata']['duracion_seg'], 60)),
        'subido': d['uploadDate'].strftime('%d-%m-%Y'),
    } for d in docs]


def listar(profesor_id):
    """Sus videos, del más nuevo al más antiguo, listos para mostrar."""
    return _presentar(list(_fichas().find({'metadata.profesor_id': profesor_id}).sort('uploadDate', -1)))


def por_id(video_ids):
    """{id: video listo para mostrar} de los que existen; los ids inválidos o borrados no aparecen."""
    oids = []
    for video_id in video_ids:
        try:
            oids.append(ObjectId(video_id))
        except (InvalidId, TypeError):
            pass
    return {v['id']: v for v in _presentar(list(_fichas().find({'_id': {'$in': oids}})))}


def enlace(ficha):
    """Enlace firmado de R2 para ver el video de esa ficha; vence (almacen_videos.DURACION_ENLACE_SEG)."""
    return almacen_videos.enlace(str(ficha['_id']))


def ficha(video_id):
    """La ficha del video (con su metadata), o None si el id no existe o no es valido."""
    try:
        oid = ObjectId(video_id)
    except (InvalidId, TypeError):
        return None
    return _fichas().find_one({'_id': oid})


def eliminar(profesor_id, video_id):
    """Borra el video si es suyo. True si lo borró.

    ValidationError si ya lo compartió con un alumno de paquete vigente (fase 4b): el alumno lo pagó y el profesor
    ya cobró su parte; borrarlo lo dejaría sin el video. Al vencer el paquete, se puede.
    """
    try:
        oid = ObjectId(video_id)
    except (InvalidId, TypeError):
        return False
    if not _fichas().find_one({'_id': oid, 'metadata.profesor_id': profesor_id}, {'_id': 1}):
        return False
    if (VideoCompartido.objects.entregados()
            .filter(video_id=str(oid), paquete__in=PaqueteClases.objects.vigentes()).exists()):
        raise ValidationError('Ya compartiste este video con un alumno que tiene su paquete vigente: '
                              'podrás borrarlo cuando el paquete venza.')
    _fichas().delete_one({'_id': oid})
    with suppress(*almacen_videos.ERRORES):  # sin ficha ya nadie lo ve: si R2 falla, solo queda un archivo huerfano
        almacen_videos.borrar(str(oid))
    return True
