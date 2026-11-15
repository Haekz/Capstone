"""Paginas legales publicas: Terminos y Condiciones y Politica de Privacidad.

Todo numero del texto (precios, plazos, vigencias, retenciones) se lee del codigo que lo aplica, no se copia: asi la
pagina no vuelve a quedar atras del sistema, como paso con el terminos_y_condiciones.txt de la raiz (precios viejos).
Quien responde por los datos sale de settings.LEGAL (context processor `datos_legales`).
"""

from django.conf import settings
from django.shortcuts import render

from agenda.cancelacion import ANTICIPACION as HORAS_CANCELA_PROFESOR
from apoderados.models import Documento
from mensajes.retencion import DIAS_SIN_ACTIVIDAD
from soporte.models import Ticket

from . import paquetes
from .aceptacion import VERSION
from .models import Inscripcion, SolicitudClaseExtra


def _horas(plazo):
    return int(plazo.total_seconds() // 3600)


def terminos(request):
    contexto = {
        'actualizado': VERSION,
        'cotizaciones': paquetes.cotizar(),
        'comision_pct': int(paquetes.COMISION * 100),
        'precio_video': paquetes.PRECIO_VIDEO,
        'max_videos_extra': paquetes.MAX_VIDEOS_EXTRA,
        'dias_entrega_extra': paquetes.DIAS_ENTREGA_EXTRA,
        'horas_cancelar': _horas(Inscripcion.ANTICIPACION_SIN_COSTO),
        'horas_cancela_profesor': _horas(HORAS_CANCELA_PROFESOR),
        'horas_respuesta_extra': _horas(SolicitudClaseExtra.PLAZO_RESPUESTA),
    }
    return render(request, 'alumnos/terminos.html', contexto)


def privacidad(request):
    contexto = {
        'actualizado': VERSION,
        'dias_documentos': Documento.VIGENCIA.days,
        'dias_mensajes': DIAS_SIN_ACTIVIDAD,
        'meses_observaciones': settings.OBSERVACIONES_MESES,
        'dias_habiles_eliminacion': Ticket.DIAS_HABILES[Ticket.PRIVACIDAD],
    }
    return render(request, 'alumnos/privacidad.html', contexto)
