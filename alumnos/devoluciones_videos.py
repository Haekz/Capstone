"""Devolucion por videos no entregados (fase 6e, decidido 09-nov): soporte la registra desde el ticket de Videos.

Primero se intenta devolver por Transbank (alumnos/reembolsos.py). Si no se puede, se transfiere a mano y eso lo aprueba
un administrador antes (13-nov): soporte pide la aprobacion (se escala al admin con un motivo armado aqui) y el admin la
deja registrada con quien y cuando. Lo que falta = lo contratado (agregado + extras pagados) - lo compartido - lo ya
devuelto: es una cuenta,
no una opinion. El monto lo calcula el servidor (valor promedio por video x cantidad); soporte nunca lo escribe.
Lo devuelto sale de lo que el profesor debe entregar (videos_extra.contratados): no puede compartirlo y cobrarlo
dos veces, ni cuenta como atraso, y lo que cobra por lo que si entrego no cambia. Los avisos y el mensaje del ticket
los pone la vista (alumnos/views_soporte_videos.py), como al retirar un video.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from soporte.tickets import escalar_al_admin, indicar

from . import paquetes, videos_compartidos, videos_extra
from .models import PaqueteClases
from .models.videos import DevolucionVideos
from .templatetags.dinero import clp


def sin_entregar(paquete):
    """Videos pagados que el profesor todavia no compartio y que tampoco se devolvieron."""
    return max(0, videos_extra.contratados(paquete) - paquete.videos_compartidos.entregados().count())


def valor_por_video(paquete):
    """Lo pagado por cada video: el promedio entre el agregado y los extra (el mismo con que se le paga al profesor)."""
    monto, videos = videos_extra.totales(paquete)
    return paquetes.valor_video(monto, videos)


def registrar(ticket, paquete_id, cantidad, agente):
    """Registra la devolucion de ``cantidad`` videos de un paquete pagado del estudiante del ticket de Videos.

    ValidationError con el motivo si no corresponde. El candado en el paquete es el mismo que usa el profesor al
    compartir: un video compartido y uno devuelto no se pisan, y dos registros seguidos no devuelven lo mismo.
    """
    try:
        paquete_id = int(paquete_id)
    except (TypeError, ValueError):
        paquete_id = None
    alumno_id = videos_compartidos.alumno_id_del_ticket(ticket)  # None si no es un ticket de Videos
    with transaction.atomic():
        paquete = (PaqueteClases.objects.select_for_update()
                   .filter(pk=paquete_id, alumno_id=alumno_id, estado=PaqueteClases.ESTADO_ACTIVA).first()
                   if alumno_id else None)
        if not paquete:
            raise ValidationError('No encontramos ese paquete entre los pagados del estudiante.')
        faltan = sin_entregar(paquete)
        if not faltan:
            raise ValidationError('A ese paquete no le faltan videos por entregar.')
        if cantidad > faltan:
            raise ValidationError(f'Solo faltan {faltan} video{"" if faltan == 1 else "s"} por entregar en ese paquete.')
        if cantidad < 1:
            raise ValidationError('Elige cu\u00e1ntos videos devolver.')
        return DevolucionVideos.objects.create(paquete=paquete, cantidad=cantidad,
                                               monto=valor_por_video(paquete) * cantidad,
                                               ticket=ticket, registrada_por=agente)


def pedir_aprobacion(devolucion, autor):
    """Soporte no pudo devolver por Transbank: escala al admin, con el monto y el motivo, para que apruebe transferir a mano.

    ValidationError si ya esta aprobada, si ya hay un pedido esperando respuesta o si el ticket ya esta escalado. Si el
    admin respondio otra cosa (no la aprobo), se puede volver a pedir.
    """
    if devolucion.aprobada:
        raise ValidationError('Esa devoluci\u00f3n ya est\u00e1 aprobada: puedes transferirla.')
    if devolucion.escalamiento_id and devolucion.escalamiento.pendiente:
        raise ValidationError('Ya pediste la aprobaci\u00f3n: espera la respuesta del administrador.')
    cantidad = f'{devolucion.cantidad} video{"" if devolucion.cantidad == 1 else "s"}'
    motivo = (f'Devolver {cantidad} sin entregar a un alumno. Transbank no pudo hacerlo'
              f'{f" ({devolucion.error_reembolso})" if devolucion.error_reembolso else ""}. '
              f'Pido aprobar transferir {clp(devolucion.por_devolver)} a mano.')
    with transaction.atomic():
        devolucion.escalamiento = escalar_al_admin(devolucion.ticket, autor, motivo)
        devolucion.save(update_fields=['escalamiento'])


def aprobar(escalamiento, admin):
    """El admin aprueba transferir a mano la devolucion que soporte pidio en ``escalamiento``. Una sola vez, todo o nada:
    queda quien y cuando, y a soporte le llega la indicacion como en cualquier caso escalado."""
    with transaction.atomic():
        devolucion = (DevolucionVideos.objects.select_for_update()
                      .filter(escalamiento=escalamiento, devuelta__isnull=True, aprobada__isnull=True).first())
        if not devolucion:
            raise ValidationError('Ese caso no tiene una devoluci\u00f3n por aprobar.')
        devolucion.aprobada, devolucion.aprobada_por = timezone.now(), admin
        devolucion.save(update_fields=['aprobada', 'aprobada_por'])
        indicar(escalamiento, admin, f'Aprobado: transfiere {clp(devolucion.por_devolver)} a mano y m\u00e1rcala devuelta.')
        return devolucion


def marcar_devuelta(ticket, devolucion_id):
    """Soporte ya transfirio el dinero a mano de una devolucion de ``ticket``. Una sola vez, y solo si el admin la aprobo.

    ValidationError si no existe o ya estaba (sin codigo), o si falta la aprobacion (codigo ``sin_aprobacion``)."""
    with transaction.atomic():
        devolucion = (DevolucionVideos.objects.select_for_update().select_related('paquete__alumno__user')
                      .filter(pk=devolucion_id, ticket=ticket, devuelta__isnull=True).first())
        if not devolucion:
            raise ValidationError('Esa devoluci\u00f3n no existe o ya est\u00e1 marcada como devuelta.')
        if not devolucion.aprobada:
            raise ValidationError('Falta la aprobaci\u00f3n del administrador para transferir a mano.', code='sin_aprobacion')
        devolucion.devuelta = timezone.now()
        devolucion.save(update_fields=['devuelta'])
        return devolucion


def casos_del_ticket(ticket):
    """Para el panel de soporte: los paquetes pagados del estudiante a los que les faltan videos (con lo que valdria
    devolver 1, 2... y el monto) y las devoluciones ya registradas en este ticket. Vacio si no es un ticket de Videos."""
    alumno_id = videos_compartidos.alumno_id_del_ticket(ticket)
    if alumno_id is None:
        return {'paquetes': [], 'devoluciones': []}
    faltantes = []
    for paquete in (PaqueteClases.objects.filter(alumno_id=alumno_id, estado=PaqueteClases.ESTADO_ACTIVA)
                    .select_related('profesor__user').order_by('-fecha_fin')):
        faltan = sin_entregar(paquete)
        if faltan:
            valor = valor_por_video(paquete)
            faltantes.append({'paquete': paquete, 'faltan': faltan,
                              'opciones': [(n, n * valor) for n in range(1, faltan + 1)]})
    return {'paquetes': faltantes, 'devoluciones': list(ticket.devoluciones_videos.select_related('paquete', 'escalamiento'))}
