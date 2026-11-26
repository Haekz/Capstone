"""Compra de paquetes con Webpay Plus (Transbank): inicio del pago y confirmacion."""

import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from lbwus.credenciales_transbank import validar_produccion

from . import aceptacion, avisos_profesor, paquetes, videos_extra
from .decorators import alumno_required
from .exceptions import InscripcionError
from .models import Alumno, CompraVideosExtra, PaqueteClases, Suscripcion
from .services import exigir_mayor_de_edad
from .templatetags.dinero import clp as _clp  # mismo formato en vistas y plantillas
from .utils import entero
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
    if not aceptacion.confirmar(request):  # sin aceptar los Terminos y la Privacidad no se cobra ni se crea el paquete
        messages.error(request, 'Para comprar debes aceptar los Términos y condiciones y la Política de privacidad.')
        return redirect('planes')

    monto = paquetes.precio(plan)
    con_videos = request.POST.get('videos') == '1'  # el navegador solo dice si lo quiere; el precio es del servidor
    if con_videos:
        try:
            videos_extra.exigir_a_la_venta()  # sin R2 no se cobra un agregado que nadie podria entregar
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return redirect('planes')
    monto_videos = paquetes.precio_agregado(plan) if con_videos else 0
    # Unico (26 caracteres, el maximo de Transbank): con un numero corto al azar, un
    # pedido abandonado podia compartir orden con una compra nueva y activarse gratis.
    buy_order = f'PQ{secrets.token_hex(12)}'
    session_id = f'S{secrets.token_hex(8)}'
    try:
        response = _tx().create(buy_order, session_id, monto + monto_videos, request.build_absolute_uri(reverse('confirmacion')))
    except Exception as error:  # Transbank caido o rechazo la orden: no se cobra ni se crea el paquete
        _log_error_transbank('create', buy_order, error, monto + monto_videos)
        return render(request, 'alumnos/confirmacion.html', {'aprobado': False, 'items': []})
    logger.info('evento=pago_iniciado tipo=paquete buy_order=%s monto=%s', buy_order, monto + monto_videos)

    with transaction.atomic():  # paquete y registro del apoderado: ambos o ninguno
        paquete = PaqueteClases.objects.create(
            alumno_id=alumno_id, profesor=profesor, plan=plan.codigo,
            clases=plan.clases, tarifa=paquetes.TARIFA, monto=monto, dias=plan.vigencia_dias,
            videos=plan.videos if con_videos else 0, monto_videos=monto_videos,
            buy_order=buy_order, token_ws=response['token'],
        )
        if al_crear:
            al_crear(paquete)
    return render(request, 'alumnos/redirect_webpay.html', {'url': response['url'], 'token': response['token']})


@alumno_required
@require_POST
def comprar_videos_extra(request):
    """Inicia Webpay por videos extra de un paquete del alumno. El monto lo calcula el servidor."""
    return iniciar_compra_videos_extra(request, request.session['alumno_id'])  # el menor no pasa: ahi se bloquea


def iniciar_compra_videos_extra(request, alumno_id, al_crear=None, vinculo=None, volver=None):
    """Unico inicio de Webpay para videos extra: lo usan el alumno y el apoderado (fase 6).

    El paquete viene del POST y debe ser de ese alumno (si no, 404); la cantidad se valida con las reglas de
    alumnos/videos_extra.py y el monto lo pone el servidor. Menores: solo compra su apoderado, con el ``vinculo``
    que lo autoriza. Se valida antes de llamar a Transbank (no se cobra lo que no se puede comprar) y otra vez
    dentro del candado del paquete, para que dos compras simultaneas no pasen del tope. ``al_crear`` recibe la
    compra dentro de la misma transaccion; ``volver`` es donde se muestra el motivo si no procede (por defecto, la
    pestana de videos del alumno).
    """
    volver = volver or reverse('alumno_pag1') + '?pestana=videos'
    alumno = get_object_or_404(Alumno, pk=alumno_id)
    try:
        exigir_mayor_de_edad(alumno, vinculo)
    except InscripcionError:
        return redirect('alumno_pag1')
    paquete = get_object_or_404(PaqueteClases, pk=entero(request.POST.get('paquete')), alumno=alumno)
    cantidad = entero(request.POST.get('cantidad')) or 0
    try:
        monto = videos_extra.validar(paquete, cantidad)
    except ValidationError as error:
        messages.error(request, error.messages[0])
        return redirect(volver)
    buy_order = f'VX{secrets.token_hex(12)}'  # 26 caracteres, el maximo de Transbank; unico como en los paquetes
    session_id = f'S{secrets.token_hex(8)}'
    try:
        response = _tx().create(buy_order, session_id, monto, request.build_absolute_uri(reverse('confirmacion')))
    except Exception as error:  # Transbank caido o rechazo la orden: no se cobra ni se crea la compra
        _log_error_transbank('create', buy_order, error, monto)
        return render(request, 'alumnos/confirmacion.html', {'aprobado': False, 'items': []})
    logger.info('evento=pago_iniciado tipo=videos_extra buy_order=%s monto=%s', buy_order, monto)
    try:
        with transaction.atomic():
            PaqueteClases.objects.select_for_update().get(pk=paquete.pk)
            videos_extra.validar(paquete, cantidad)
            compra = CompraVideosExtra.objects.create(
                paquete=paquete, cantidad=cantidad, monto=monto, buy_order=buy_order, token_ws=response['token'])
            if al_crear:
                al_crear(compra)
    except ValidationError as error:  # otra compra se adelanto: el token de Transbank queda sin usar
        messages.error(request, error.messages[0])
        return redirect(volver)
    return render(request, 'alumnos/redirect_webpay.html', {'url': response['url'], 'token': response['token']})


def _log_error_transbank(etapa, buy_order, error, monto=None):
    """Una linea por fallo de Transbank (red, credenciales o rechazo de la orden).

    Solo el tipo del error: su texto puede traer la URL con el token. Nunca el token ni datos de tarjeta.
    """
    logger.error('evento=pago_error_transbank etapa=%s buy_order=%s monto=%s error=%s',
                 etapa, buy_order or '-', '-' if monto is None else monto, type(error).__name__)


def _orden_del_token(token):
    """La orden de compra de un token que creamos nosotros, o '-' (no se registra lo que manda el navegador)."""
    if not token:
        return '-'
    for modelo in (PaqueteClases, CompraVideosExtra):
        orden = modelo.objects.filter(token_ws=token).values_list('buy_order', flat=True).first()
        if orden:
            return orden
    return '-'


def _avisar_profesor(aviso, pago):
    """Avisa al profesor de un pago. El pago ya esta confirmado: un fallo aqui se registra y no lo tumba."""
    try:
        aviso(pago)
    except Exception:
        logger.exception('No se pudo avisar al profesor (%r, pago %s)', aviso, pago.pk)


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
    compra = CompraVideosExtra.objects.filter(buy_order=buy_order).first() if buy_order else None
    esperado = paquete.total if paquete else compra.monto if compra else None
    monto_distinto = esperado is not None and int(resp.get('amount') or 0) != esperado
    if monto_distinto:
        aprobado = False
    Suscripcion.confirmar_pago(buy_order, aprobado)
    autorizacion, fecha = resp.get('authorization_code') or '', parse_datetime(resp.get('transaction_date') or '')
    activados = PaqueteClases.confirmar_pago(buy_order, aprobado, autorizacion, fecha)
    extras_activados = CompraVideosExtra.confirmar_pago(buy_order, aprobado, autorizacion, fecha)
    # Despues de guardar: si la confirmacion local falla, no queda un "aprobado" que nunca se activo.
    if buy_order:  # sin orden (commit caido) ya quedo el pago_error_transbank
        motivo = ' motivo=monto_distinto' if monto_distinto else ' motivo=orden_desconocida' if esperado is None else ''
        (logger.warning if motivo else logger.info)(
            'evento=%s buy_order=%s monto=%s esperado=%s estado=%s codigo=%s activados=%s%s',
            'pago_aprobado' if aprobado else 'pago_rechazado', buy_order, resp.get('amount'),
            '-' if esperado is None else esperado, resp.get('status') or '-', resp.get('response_code'),
            len(activados) + len(extras_activados), motivo)
    # Solo lo que ESTA llamada activo: el aviso al profesor sale una vez por compra, aunque el retorno llegue dos veces.
    for paquete in activados:
        if paquete.videos:
            transaction.on_commit(lambda paquete=paquete: _avisar_profesor(avisos_profesor.agregado_videos, paquete))
    for compra in extras_activados:
        transaction.on_commit(lambda compra=compra: _avisar_profesor(avisos_profesor.videos_extra_comprados, compra))
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
        except Exception as error:
            _log_error_transbank('commit', _orden_del_token(token), error)
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
        ] + [
            {'titulo': f'Videos extra: {c.cantidad} video{"s" if c.cantidad != 1 else ""} de apoyo',
             'cantidad': 1, 'precio': _clp(c.monto)}
            for c in (CompraVideosExtra.objects.filter(buy_order=buy_order) if buy_order else [])
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
        # El alumno anulo en Webpay (o volvio con los dos tokens, BUG-QA-02): no se cobra.
        logger.info('evento=pago_anulado buy_order=%s', _orden_del_token(tbk_token))
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
