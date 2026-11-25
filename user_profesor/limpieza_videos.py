"""Borrado de videos sin actividad (decidido 23-nov): 30 dias sin reproducirse, con aviso 7 dias antes.

- Actividad = lo mas reciente entre la subida, la ultima vez que se compartio y la ultima vez que alguien lo abrio
  (alumno, apoderado o soporte: videoteca.registrar_vista).
- A los 23 dias sin actividad se avisa, por campanita y correo, al profesor y a los alumnos con paquete vigente que lo
  tienen (si es menor, a sus apoderados). Se borra recien 7 dias despues de ese aviso: aunque el cron se salte dias,
  nadie pierde un video sin una semana de aviso. Si alguien lo ve o se comparte despues del aviso, vuelve a contar.
- Se borra aunque este compartido con un paquete vigente (decidido 23-nov: con aviso). No se borra mientras un
  reclamo abierto de Videos de apoyo lo nombre (soporte puede necesitar revisarlo).
Corre a diario: tareas_diarias -> borrar_videos_inactivos.
"""

from datetime import timedelta, timezone as tz

from django.db.models import Max
from django.utils import timezone

from agenda import avisos_alumno
from alumnos import avisos_profesor
from alumnos.models import PaqueteClases, Profesor
from alumnos.models.videos import VideoCompartido
from alumnos.videos_compartidos import ID_VIDEO
from soporte.models import Ticket

from . import videoteca

DIAS_SIN_ACTIVIDAD = 30
DIAS_AVISO = 7


def _utc(momento):
    """MongoDB entrega las fechas en UTC; mongomock (pruebas) sin zona horaria."""
    if momento is None or timezone.is_aware(momento):
        return momento
    return momento.replace(tzinfo=tz.utc)


def _en_reclamo():
    """Ids de video que nombra algun reclamo abierto de Videos de apoyo."""
    abiertos = Ticket.objects.filter(estado=Ticket.ABIERTO, categoria=Ticket.VIDEOS).values_list('descripcion', flat=True)
    return {video_id for descripcion in abiertos for video_id in ID_VIDEO.findall(descripcion)}


def _avisar(ficha, video_id, fecha):
    """Campanita y correo al profesor dueno y a quienes lo tienen con paquete vigente."""
    titulo = ficha['metadata']['titulo']
    profesor = Profesor.objects.filter(id_profesor=ficha['metadata']['profesor_id']).select_related('user').first()
    if profesor:
        avisos_profesor.video_por_borrarse(profesor, titulo, fecha)
    alumnos = {c.paquete.alumno for c in VideoCompartido.objects.entregados()
               .filter(video_id=video_id, paquete__in=PaqueteClases.objects.vigentes())
               .select_related('paquete__alumno__user')}
    for alumno in alumnos:
        avisos_alumno.video_por_borrarse(alumno, titulo, fecha)


def revisar(ahora=None):
    """Avisa lo que lleva 23 dias sin actividad y borra lo avisado hace 7. Devuelve (avisados, borrados)."""
    ahora = ahora or timezone.now()
    fichas = videoteca.todas()
    compartidos = dict(VideoCompartido.objects.filter(video_id__in=[str(f['_id']) for f in fichas])
                       .values('video_id').annotate(ultimo=Max('compartido')).values_list('video_id', 'ultimo'))
    protegidos = _en_reclamo()
    avisados = borrados = 0
    for ficha in fichas:
        video_id = str(ficha['_id'])
        if video_id in protegidos:
            continue
        actividad = max(m for m in (_utc(ficha['uploadDate']), _utc(ficha.get('ultima_vista')),
                                    compartidos.get(video_id)) if m)
        aviso = _utc(ficha.get('aviso_borrado'))
        if aviso and aviso < actividad:
            aviso = None  # alguien lo vio o se compartio despues del aviso: vuelve a contar
        if aviso is None:
            if ahora >= actividad + timedelta(days=DIAS_SIN_ACTIVIDAD - DIAS_AVISO):
                _avisar(ficha, video_id, timezone.localdate(ahora + timedelta(days=DIAS_AVISO)))
                videoteca.marcar_aviso(ficha['_id'], ahora)
                avisados += 1
        elif ahora >= aviso + timedelta(days=DIAS_AVISO):
            videoteca.borrar(ficha['_id'])
            borrados += 1
    return avisados, borrados
