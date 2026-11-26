"""Videos de apoyo del profesor (agregado de videos, fase 1).

El archivo vive en Cloudflare R2 (almacen_videos.py) y su ficha (titulo, materia, duracion, dueno) es la tabla Video de
PostgreSQL, con el mismo id: el video_id de VideoCompartido y el que nombran los reclamos de soporte. Sin las variables
R2_* los videos quedan desactivados (ERRORES): ni se listan ni se suben.

El profesor sube MP4 de hasta 30 minutos por cada materia que enseña (sus Clase). La duración se lee de la
caja mvhd del propio MP4: no hace falta instalar ffmpeg. La materia se guarda por id: si el admin la renombra, se
ve el nombre nuevo.
"""

import logging
import struct

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.utils import timezone

from alumnos.models import Asignatura, Clase, PaqueteClases, Video, VideoCompartido
from alumnos.models.videos import nuevo_id_video

from . import almacen_videos

logger = logging.getLogger(__name__)

ERRORES = almacen_videos.ERRORES  # "los videos no estan disponibles": lo que hay que atrapar
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
    """Las fichas. Sin R2 configurado los videos estan desactivados: AlmacenNoConfigurado, aunque haya fichas."""
    almacen_videos.exigir_configurado()
    return Video.objects


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
    video_id = nuevo_id_video()  # antes de subir: el archivo en R2 se llama igual que su ficha
    almacen_videos.guardar(video_id, archivo)
    try:
        Video.objects.create(id=video_id, profesor_id=profesor_id, asignatura_id=int(asignatura), titulo=titulo,
                             duracion_seg=round(duracion))
    except DatabaseError:
        _borrar_archivo(video_id)  # sin ficha nadie lo veria: no dejar el archivo huerfano en R2
        raise
    return video_id


def _presentar(videos):
    """Fichas convertidas a lo que se muestra: id, titulo, materia, duracion y fecha."""
    return [{
        'id': v.pk,
        'titulo': v.titulo,
        'asignatura': v.asignatura.nombre if v.asignatura else 'Materia eliminada',
        'duracion': '{}:{:02d}'.format(*divmod(v.duracion_seg, 60)),
        'subido': timezone.localtime(v.subido).strftime('%d-%m-%Y'),
    } for v in videos]


def listar(profesor_id):
    """Sus videos, del más nuevo al más antiguo, listos para mostrar."""
    return _presentar(_fichas().filter(profesor_id=profesor_id).select_related('asignatura'))


def por_id(video_ids):
    """{id: video listo para mostrar} de los que existen; los ids inválidos o borrados no aparecen."""
    return {v['id']: v for v in _presentar(_fichas().filter(pk__in=[str(i) for i in video_ids])
                                                   .select_related('asignatura'))}


def enlace(ficha):
    """Enlace firmado de R2 para ver el video de esa ficha; vence (almacen_videos.DURACION_ENLACE_SEG)."""
    return almacen_videos.enlace(ficha.pk)


def ficha(video_id):
    """La ficha del video, o None si el id no existe."""
    return _fichas().filter(pk=str(video_id)).first() if video_id else None


def todas():
    """Las fichas de todos los videos, con su profesor (para la limpieza diaria, limpieza_videos.py)."""
    return list(_fichas().select_related('profesor__user'))


def registrar_vista(video_id):
    """Anota que alguien abrio el video ahora: cuenta como actividad para no borrarlo (limpieza_videos.py)."""
    _fichas().filter(pk=video_id).update(ultima_vista=timezone.now())


def marcar_aviso(video_id, cuando):
    """Anota que ya se aviso que el video se borrara: el borrado ocurre 7 dias despues (limpieza_videos.py)."""
    _fichas().filter(pk=video_id).update(aviso_borrado=cuando)


def _borrar_archivo(video_id):
    """Quita el archivo de R2. Si R2 falla, queda un archivo huerfano que nadie puede ver: se registra su id (nunca el
    titulo) para quitarlo a mano desde el panel de Cloudflare."""
    try:
        almacen_videos.borrar(video_id)
    except almacen_videos.ERRORES as exc:
        logger.warning('No se pudo borrar de R2 el video %s (%s): quitarlo a mano.', video_id, type(exc).__name__)


def borrar(video_id):
    """Quita la ficha y el archivo de R2. Quien llama ya decidio que se puede borrar."""
    Video.objects.filter(pk=video_id).delete()
    _borrar_archivo(video_id)


def borrar_del_profesor(profesor):
    """Todos sus videos, al eliminar su cuenta (supresiones/datos_propios.py): su cara y su voz son datos personales.
    Sin R2 configurado se quitan igual las fichas; el archivo que quede se registra para quitarlo a mano."""
    for video_id in list(Video.objects.filter(profesor=profesor).values_list('pk', flat=True)):
        borrar(video_id)


def eliminar(profesor_id, video_id):
    """Borra el video si es suyo. True si lo borró.

    ValidationError si ya lo compartió con un alumno de paquete vigente (fase 4b): el alumno lo pagó y el profesor
    ya cobró su parte; borrarlo lo dejaría sin el video. Al vencer el paquete, se puede.
    """
    if not _fichas().filter(pk=str(video_id), profesor_id=profesor_id).exists():
        return False
    if (VideoCompartido.objects.entregados()
            .filter(video_id=video_id, paquete__in=PaqueteClases.objects.vigentes()).exists()):
        raise ValidationError('Ya compartiste este video con un alumno que tiene su paquete vigente: '
                              'podrás borrarlo cuando el paquete venza.')
    borrar(video_id)
    return True
