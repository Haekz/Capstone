"""Compra de paquetes con Webpay Plus (Transbank): inicio del pago y confirmacion."""

import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from lbwus.credenciales_transbank import validar_produccion

from . import avisos_profesor, paquetes
from .decorators import alumno_required
from .exceptions import InscripcionError
from .models import Alumno, PaqueteClases, Suscripcion
from .services import exigir_mayor_de_edad
from .templatetags.dinero import clp as _clp  # mismo formato en vistas y plantillas
from .views import _profesor_habilitado

logger = logging.getLogger(__name__)


# ============================================================
# TRANSBANK - WEBPAY PLUS
# Ambiente de integración
# ============================================================

from transbank.webpay.webpay_plus.transaction import Transaction
from transbank.common.options import WebpayOptions
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.integration_type import IntegrationType


def _tx():
    """Construye la instancia de Transaction de Webpay Plus según la estrategia de credenciales (S-08 / 7.6).

    Salvaguarda estricta:
    - Salvo que TRANSBANK_PRODUCCION_HABILITADA sea True Y se provean credenciales válidas en LIVE,
      el sistema opera forzosamente en IntegrationType.TEST (Sandbox oficial Transbank).
    - Con produccion habilitada, si falta cualquier dato se levanta ImproperlyConfigured (no se vuelve a TEST).
    - Evita cualquier cobro real o uso no autorizado en ambientes de prueba o desarrollo.
    """
    produccion_habilitada = getattr(settings, 'TRANSBANK_PRODUCCION_HABILITADA', False)
    cc = getattr(settings, 'TRANSBANK_COMMERCE_CODE', '')
    api_key = getattr(settings, 'TRANSBANK_API_KEY', '')
    env_str = getattr(settings, 'TRANSBANK_ENVIRONMENT', 'TEST')

    validar_produccion(produccion_habilitada, env_str, cc, api_key)
    if produccion_habilitada:
        return Transaction(
            WebpayOptions(
                cc,
                api_key,
                IntegrationType.LIVE,
            )
        )

    # Por defecto / Salvaguarda de no cobro real (Modo Integración / Sandbox oficial):
    return Transaction(
        WebpayOptions(
            IntegrationCommerceCodes.WEBPAY_PLUS,
            IntegrationApiKeys.WEBPAY,
            IntegrationType.TEST,
        )
    )


# ============================================================
# PAGO CON WEBPAY PLUS - TRANSBANK
# ============================================================

@alumno_required  # el paquete necesita un dueño: sin alumna logueada no se cobra
@require_POST
def comprar_paquete(request):
    """Inicia Webpay por un paquete. El monto lo calcula el servidor con la tarifa del profesor."""
    return iniciar_compra_paquete(request, request.session['alumno_id'])  # el menor no pasa: ahi se bloquea


def iniciar_compra_paquete(request, alumno_id, al_crear=None, vinculo=None):
    """Unico inicio de Webpay para paquetes: lo usan el alumno y el apoderado.

    Plan y profesor vienen del POST; el monto lo calcula el servidor. ``al_crear``
    recibe el paquete dentro de la misma transaccion (la compra del apoderado).

    Menores: solo contrata su apoderado, con el ``vinculo`` que lo autoriza. El bloqueo vive aqui y no en las
    vistas, porque aqui se crea el paquete: cualquier vista nueva que llegue hasta este punto queda cubierta.
    """
    try:
        exigir_mayor_de_edad(get_object_or_404(Alumno, pk=alumno_id), vinculo)
    except InscripcionError:
        return redirect('alumno_pag1')
    plan = paquetes.POR_CODIGO.get(request.POST.get('plan', ''))
    profesor = _profesor_habilitado(request.POST.get('profesor'))
    if not (plan and profesor):
        return redirect('planes')

    monto = paquetes.precio(plan, profesor.tarifa)
    con_videos = request.POST.get('videos') == '1'  # el navegador solo dice si lo quiere; el precio es del servidor
    monto_videos = paquetes.precio_agregado(plan) if con_videos else 0
    # Unico (26 caracteres, el maximo de Transbank): con un numero corto al azar, un
    # pedido abandonado podia compartir orden con una compra nueva y activarse gratis.
    buy_order = f'PQ{secrets.token_hex(12)}'
    session_id = f'S{secrets.token_hex(8)}'
    try:
        response = _tx().create(buy_order, session_id, monto + monto_videos, request.build_absolute_uri(reverse('confirmacion')))
    except Exception:  # Transbank caido o rechazo la orden: no se cobra ni se crea el paquete
        return render(request, 'alumnos/confirmacion.html', {'aprobado': False, 'items': []})

    with transaction.atomic():  # paquete y registro del apoderado: ambos o ninguno
        paquete = PaqueteClases.objects.create(
            alumno_id=alumno_id, profesor=profesor, plan=plan.codigo,
            clases=plan.clases, tarifa=profesor.tarifa, monto=monto, dias=plan.vigencia_dias,
            videos=plan.videos if con_videos else 0, monto_videos=monto_videos,
            buy_order=buy_order, token_ws=response['token'],
        )
        if al_crear:
            al_crear(paquete)
    return render(request, 'alumnos/redirect_webpay.html', {'url': response['url'], 'token': response['token']})


def _avisar_agregado(paquete):
    """Avisa al profesor del agregado de videos. El pago ya esta confirmado: un fallo aqui se registra y no lo tumba."""
    try:
        avisos_profesor.agregado_videos(paquete)
    except Exception:
        logger.exception('No se pudo avisar al profesor del agregado de videos (paquete %s)', paquete.pk)


def registrar_respuesta(resp):
    """Aplica a la orden lo que Transbank respondio (commit al volver el alumno, o status al revisar despues).

    Aprobado = codigo 0, AUTHORIZED y el monto de la orden. Idempotente: solo toca paquetes pendientes.
    Devuelve (aprobado, buy_order).
    """
    aprobado = (
        resp.get('response_code') == 0
        and resp.get('status') == 'AUTHORIZED'
    )
    buy_order = resp.get('buy_order', '')
    paquete = PaqueteClases.objects.filter(buy_order=buy_order).first() if buy_order else None
    if paquete and int(resp.get('amount') or 0) != paquete.total:
        aprobado = False
    Suscripcion.confirmar_pago(buy_order, aprobado)
    activados = PaqueteClases.confirmar_pago(buy_order, aprobado, resp.get('authorization_code') or '',
                                             parse_datetime(resp.get('transaction_date') or ''))
    for paquete in activados:  # solo los que ESTA llamada activo: el aviso sale una vez por compra
        if paquete.videos:
            transaction.on_commit(lambda paquete=paquete: _avisar_agregado(paquete))
    return aprobado, buy_order


@csrf_exempt
def confirmacion(request):

    token = (
        request.GET.get('token_ws')
        or request.POST.get('token_ws')
    )

    tbk_token = (
        request.GET.get('TBK_TOKEN')
        or request.POST.get('TBK_TOKEN')
    )

    ctx = {
        'items': []
    }

    # Pago recibido desde Webpay (con TBK_TOKEN tambien, es invalido: no se confirma, BUG-QA-02)

    if token and not tbk_token:

        try:
            resp = _tx().commit(token)
        except Exception:
            resp = {}

        card = resp.get('card_detail') or {}
        aprobado, buy_order = registrar_respuesta(resp)
        de_la_orden = list(PaqueteClases.objects.filter(buy_order=buy_order).select_related('profesor__user')) if buy_order else []
        ctx['items'] = [
            {'titulo': f'{p.get_plan_display()}: {p.clases} clase(s) con {p.profesor.nombre if p.profesor else "—"}',
             'cantidad': 1, 'precio': _clp(p.monto)}
            for p in de_la_orden
        ] + [
            {'titulo': f'Agregado: {p.videos} video{"s" if p.videos != 1 else ""} de ayuda', 'cantidad': 1, 'precio': _clp(p.monto_videos)}
            for p in de_la_orden if p.monto_videos
        ]

        ctx.update({
            'aprobado': aprobado,
            'orden': buy_order,
            'monto': _clp(resp.get('amount') or 0),
            'codigo_autorizacion': resp.get('authorization_code', ''),
            'tarjeta': card.get('card_number', ''),
            'fecha': resp.get('transaction_date', ''),
        })
    elif tbk_token:
        ctx.update({
            'aprobado': False,
            'anulado': True
        })
    else:
        return redirect('planes')
    return render(
        request,
        'alumnos/confirmacion.html',
        ctx
    )
