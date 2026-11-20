"""Clase extra desde la ventana de horarios: las horas que se pueden pedir y el pedido (tramo B).

Las reglas viven en clase_extra.py; aqui solo se lee la peticion y se responde como la reserva normal,
{success, message}, con un mensaje listo para mostrarle al alumno.
"""

import json
from datetime import date

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from agenda.models import HorarioSemanal

from . import clase_extra
from .decorators import alumno_required_json
from .exceptions import InscripcionError
from .models import Alumno, Clase

DIAS_DE_LA_SEMANA = dict(HorarioSemanal.DIAS)


def _error(mensaje, status=400):
    return JsonResponse({'success': False, 'message': mensaje}, status=status)


def _clase(valor):
    """La clase pedida, o None si el id no es un numero o no existe."""
    if not str(valor or '').isdigit():
        return None
    return Clase.objects.select_related('profesor', 'asignatura').filter(pk=int(valor)).first()


def _cuando(momento):
    """'lunes 16/11 a las 14:00': el plazo vence a mas tardar en 24 horas, el anio sobra."""
    local = timezone.localtime(momento)
    return f"{DIAS_DE_LA_SEMANA[local.weekday()].lower()} {local:%d/%m} a las {local:%H:%M}"


@alumno_required_json
def horas_clase_extra(request):
    """GET ?clase_id=&fecha=AAAA-MM-DD: las horas de ese dia, cada una con el motivo si no se puede pedir."""
    alumno = get_object_or_404(Alumno, id_alumno=request.session['alumno_id'])
    clase = _clase(request.GET.get('clase_id'))
    if clase is None:
        return _error('Clase no encontrada.', 404)
    try:
        fecha = date.fromisoformat(request.GET.get('fecha', ''))
    except ValueError:
        return _error('Elige un día válido.')
    if fecha < timezone.localdate():
        return _error('Elige un día de hoy en adelante.')
    try:
        horas = clase_extra.horas_para_pedir(alumno, clase, fecha)
    except InscripcionError as exc:
        return _error(exc.messages[0])
    return JsonResponse({'success': True, 'fecha': fecha.isoformat(), 'horas': [
        {'inicio': inicio.isoformat(), 'hora': timezone.localtime(inicio).strftime('%H:%M'), 'motivo': motivo}
        for inicio, motivo in horas
    ]})


@alumno_required_json
def pedir_clase_extra(request):
    """POST JSON {clase_id, inicio (ISO con zona), mensaje}: registra el pedido y avisa al profesor."""
    if request.method != 'POST':
        return _error('Método no permitido.', 405)
    alumno = get_object_or_404(Alumno, id_alumno=request.session['alumno_id'])
    try:
        datos = json.loads(request.body.decode('utf-8') or '{}')
    except ValueError:
        return _error('No pudimos leer tu pedido. Inténtalo de nuevo.')
    clase = _clase(datos.get('clase_id'))
    if clase is None:
        return _error('Clase no encontrada.', 404)
    try:
        inicio = parse_datetime(str(datos.get('inicio') or ''))
    except ValueError:
        inicio = None
    if inicio is None or timezone.is_naive(inicio):
        return _error('Elige un día y una hora.')
    mensaje = datos.get('mensaje') or ''
    if not isinstance(mensaje, str):
        return _error('El mensaje para el profesor tiene que ser un texto.')
    try:
        solicitud = clase_extra.solicitar(alumno, clase, inicio, mensaje)
    except InscripcionError as exc:
        return _error(exc.messages[0])
    return JsonResponse({
        'success': True,
        'message': f'Le enviamos tu pedido a {clase.profesor.nombre}. '
                   f'Tiene hasta el {_cuando(solicitud.vence_el)} para responder.',
        'vence_el': solicitud.vence_el.isoformat(),
    })
