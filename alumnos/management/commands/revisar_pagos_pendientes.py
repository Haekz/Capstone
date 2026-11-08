"""python manage.py revisar_pagos_pendientes   (tarea diaria)

Le pregunta a Transbank por los paquetes que siguen pendientes despues de una hora:
- Pagado pero el alumno no volvio a LBWUS (cerro la pestana, se cayo la conexion): se activa.
- Abandonado o rechazado en Webpay: queda rechazado, y deja de aparecer como pendiente.
Usa la misma regla que el retorno del alumno (alumnos.webpay.registrar_respuesta): codigo 0, AUTHORIZED y el
monto de la orden. Es idempotente: repetirlo no cambia lo ya resuelto.

Si Transbank no responde, el paquete sigue pendiente y se informa; se revisa en la proxima corrida.
Los pendientes anteriores al campo token_ws no se pueden consultar y quedan para soporte.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from alumnos import webpay
from alumnos.models import PaqueteClases

ESPERA = timedelta(hours=1)  # el alumno puede seguir pagando en el formulario de Webpay


class Command(BaseCommand):
    help = 'Activa o rechaza los paquetes pendientes consultando su estado en Transbank.'

    def handle(self, *args, **opciones):
        pendientes = (PaqueteClases.objects
                      .filter(estado=PaqueteClases.ESTADO_PENDIENTE, creada__lt=timezone.now() - ESPERA)
                      .exclude(token_ws=''))
        activados = rechazados = sin_respuesta = 0
        for paquete in pendientes:
            try:
                respuesta = webpay._tx().status(paquete.token_ws)
            except Exception:  # Transbank caido o token vencido: se vuelve a intentar en la proxima corrida
                sin_respuesta += 1
                continue
            if respuesta.get('buy_order') != paquete.buy_order:  # no es la orden que se pregunto: no se decide nada
                sin_respuesta += 1
                continue
            aprobado, _ = webpay.registrar_respuesta(respuesta)
            activados += aprobado
            rechazados += not aprobado
        self.stdout.write(f'Pagos pendientes revisados: {activados} activados, {rechazados} rechazados, '
                          f'{sin_respuesta} sin respuesta de Transbank.')
