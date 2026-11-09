"""Entrega de videos del profesor (agregado de videos, fase 3a): a quién le debe videos y compartirlos.

Reglas: solo videos de su biblioteca, solo a paquetes suyos y vigentes, sin pasar de los que el alumno pagó, y
nunca el mismo video dos veces al mismo alumno (si renueva, contenido nuevo). Las fechas límite salen del plan
(alumnos/paquetes.py) y se cuentan desde el pago. Del alumno solo se muestra el nombre de pila.
"""

from datetime import datetime, timedelta
from datetime import timezone as zona

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from alumnos import paquetes
from alumnos.models import PaqueteClases
from alumnos.models.videos import VideoCompartido
from alumnos.utils import es_menor
from apoderados.correo import avisar_video_por_revisar

from . import videoteca

SIN_FECHA = datetime.max.replace(tzinfo=zona.utc)


def con_agregado():
    """Paquetes vigentes con agregado de videos, con cuántos lleva compartidos (``compartidos``)."""
    return (PaqueteClases.objects.vigentes().filter(videos__gt=0)
            .select_related('alumno__user').annotate(compartidos=Count('videos_compartidos')))


def estado(paquete, ahora):
    """Cuántos faltan para la próxima fecha límite que todavía no se cumple, y si ya se pasó.
    ``paquete`` viene de con_agregado(). También lo usan los avisos diarios (plazos_videos.py)."""
    inicio = paquete.fecha_fin - timedelta(days=paquete.dias)
    for limite, acumulado in paquetes.fechas_entrega(paquetes.POR_CODIGO[paquete.plan], inicio):
        if acumulado > paquete.compartidos:
            return limite, acumulado - paquete.compartidos, limite < ahora
    return None, 0, False


def pendientes(profesor_id, ahora=None):
    """Sus alumnos con agregado de videos vigente: las entregas atrasadas primero, luego la fecha más próxima."""
    ahora = ahora or timezone.now()
    filas = []
    for paquete in con_agregado().filter(profesor_id=profesor_id):
        limite, falta, atrasada = estado(paquete, ahora)
        filas.append((atrasada, limite, {
            'paquete': paquete.pk, 'alumno': paquete.alumno.user.first_name, 'plan': paquete.get_plan_display(),
            'compartidos': paquete.compartidos, 'videos': paquete.videos, 'falta': falta, 'atrasada': atrasada,
            'proxima': timezone.localtime(limite).strftime('%d-%m-%Y') if limite else None,
        }))
    filas.sort(key=lambda f: (not f[0], f[1] or SIN_FECHA))
    return [fila for _, _, fila in filas]


def compartir(profesor_id, paquete_id, video_id):
    """Le comparte un video de su biblioteca al alumno del paquete. ValidationError con el motivo si no corresponde."""
    try:
        paquete_id = int(paquete_id)
    except (TypeError, ValueError):
        paquete_id = None
    with transaction.atomic():  # el candado en el paquete evita pasarse de los videos pagados si llegan dos juntos
        paquete = (PaqueteClases.objects.vigentes().select_for_update()
                   .filter(pk=paquete_id, profesor_id=profesor_id, videos__gt=0).first())
        if not paquete:
            raise ValidationError('No encontramos un paquete vigente con videos para ese alumno.')
        ficha = videoteca.ficha(video_id)
        if not ficha or ficha['metadata']['profesor_id'] != profesor_id:
            raise ValidationError('No encontramos ese video en tu biblioteca.')
        if paquete.videos_compartidos.count() >= paquete.videos:
            raise ValidationError(f'Ya compartiste los {paquete.videos} videos que contrató.')
        if VideoCompartido.objects.filter(paquete__alumno_id=paquete.alumno_id, video_id=str(ficha['_id'])).exists():
            raise ValidationError('Ya le compartiste este video a ese alumno. Elige uno nuevo.')
        compartido = VideoCompartido.objects.create(paquete=paquete, video_id=str(ficha['_id']))
    alumno = paquete.alumno
    if es_menor(alumno.user):  # su apoderado lo revisa y lo habilita antes de que lo vea; robust: el aviso no tumba nada
        transaction.on_commit(lambda: avisar_video_por_revisar(alumno), robust=True)
    return compartido
