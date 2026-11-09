"""Videos de apoyo del profesor (agregado de videos, fase 1): se guardan en MongoDB con GridFS.

El profesor sube MP4 de hasta 30 minutos por cada materia que enseña (sus Clase). La duración se lee de la
caja mvhd del propio MP4: no hace falta instalar ffmpeg. Sin MONGODB_URI los videos quedan desactivados
(comunidad.mongo lanza MongoNoConfigurado). La materia se guarda por id: si el admin la renombra, se ve el
nombre nuevo.
"""

import struct

from bson import ObjectId
from bson.errors import InvalidId
from django.core.exceptions import ValidationError
from gridfs import GridFSBucket

from alumnos.models import Asignatura, Clase
from comunidad import mongo

BUCKET = 'videos'
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


def _bucket():
    return GridFSBucket(mongo.get_db(), bucket_name=BUCKET)


def _archivos():
    return mongo.get_db()[f'{BUCKET}.files']


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
    metadata = {'profesor_id': profesor_id, 'asignatura_id': int(asignatura), 'titulo': titulo, 'duracion_seg': round(duracion)}
    return str(_bucket().upload_from_stream(archivo.name, archivo, metadata=metadata))


def _presentar(docs):
    """Documentos de GridFS convertidos a lo que se muestra: id, titulo, materia, duracion y fecha."""
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
    return _presentar(list(_archivos().find({'metadata.profesor_id': profesor_id}).sort('uploadDate', -1)))


def por_id(video_ids):
    """{id: video listo para mostrar} de los que existen; los ids inválidos o borrados no aparecen."""
    oids = []
    for video_id in video_ids:
        try:
            oids.append(ObjectId(video_id))
        except (InvalidId, TypeError):
            pass
    return {v['id']: v for v in _presentar(list(_archivos().find({'_id': {'$in': oids}})))}


def abrir(oid):
    """Lector del archivo (con seek y read) para entregarlo por partes; quien lo abre debe cerrarlo."""
    return _bucket().open_download_stream(oid)


def ficha(video_id):
    """El documento del video en GridFS (con su metadata), o None si el id no existe o no es valido."""
    try:
        oid = ObjectId(video_id)
    except (InvalidId, TypeError):
        return None
    return _archivos().find_one({'_id': oid})


def eliminar(profesor_id, video_id):
    """Borra el video si es suyo. True si lo borró."""
    try:
        oid = ObjectId(video_id)
    except (InvalidId, TypeError):
        return False
    if not _archivos().find_one({'_id': oid, 'metadata.profesor_id': profesor_id}, {'_id': 1}):
        return False
    _bucket().delete(oid)
    return True
