"""python manage.py revisar_pagos_pendientes   (tarea diaria)

Le pregunta a Transbank por los paquetes y las compras de videos extra que siguen pendientes despues de una hora:
- Pagado pero el alumno no volvio a LBWUS (cerro la pestana, se cayo la conexion): se activa.
- Abandonado o rechazado en Webpay: queda rechazado, y deja de aparecer como pendiente.
Usa la misma regla que el retorno del alumno (alumnos.webpay.registrar_respuesta): codigo 0, AUTHORIZED y el
monto de la orden. Es idempotente: repetirlo no cambia lo ya resuelto.

Si Transbank no responde, el paquete sigue pendiente y se informa; se revisa en la proxima corrida.
Los pendientes anteriores al campo token_ws no se pueden consultar y quedan para soporte.
"""

import logging
from datetime import timedelta
from itertools import chain

from django.core.management.base import BaseCommand
from django.utils import timezone

from alumnos import webpay
from alumnos.models import CompraVideosExtra, PaqueteClases

logger = logging.getLogger(__name__)

ESPERA = timedelta(hours=1)  # el alumno puede seguir pagando en el formulario de Webpay
EXPIRACION_MAXIMA = timedelta(days=2)  # tokens expirados en Transbank no deben bloquear cuotas para siempre


class Command(BaseCommand):
    help = 'Activa o rechaza los paquetes pendientes consultando su estado en Transbank.'

    def handle(self, *args, **opciones):
        ahora = timezone.now()
        limite = ahora - ESPERA
        limite_expirado = ahora - EXPIRACION_MAXIMA
        pendientes = chain(*(modelo.objects.filter(estado=modelo.ESTADO_PENDIENTE, creada__lt=limite)
                             .exclude(token_ws='') for modelo in (PaqueteClases, CompraVideosExtra)))
        activados = rechazados = sin_respuesta = 0
        for paquete in pendientes:
            try:
                respuesta = webpay._tx().status(paquete.token_ws)
            except Exception as exc:  # Transbank caido o token vencido
                logger.warning('Error consultando estado Transbank (%s): %s', paquete.buy_order, exc)
                if paquete.creada < limite_expirado:
                    type(paquete).confirmar_pago(paquete.buy_order, False)
                    rechazados += 1
                else:
                    sin_respuesta += 1
                continue
            if respuesta.get('buy_order') != paquete.buy_order:  # no es la orden que se pregunto: no se decide nada
                sin_respuesta += 1
                continue
            try:
                aprobado, _ = webpay.registrar_respuesta(respuesta)
            except Exception:
                logger.exception('Error aplicando respuesta Transbank (%s)', paquete.buy_order)
                sin_respuesta += 1
                continue
            activados += aprobado
            rechazados += not aprobado
        self.stdout.write(f'Pagos pendientes revisados: {activados} activados, {rechazados} rechazados, '
                          f'{sin_respuesta} sin respuesta de Transbank.')
