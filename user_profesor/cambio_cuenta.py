"""Cambio de la cuenta bancaria del profesor (paso 3b, decisiones P3 y N2).

Cambiar una cuenta existente exige la contrasena (en la vista) y un enlace al
correo registrado. El enlace lleva los datos nuevos, con el numero ya cifrado, y
la fecha de la ultima modificacion de la cuenta: sirve una sola vez y deja de
servir si la cuenta cambia por otro lado. Asi no hace falta una tabla nueva.
"""

from datetime import timedelta

from django.core import signing
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from alumnos.correo import enviar
from alumnos.models import CuentaBancaria

SAL = 'user_profesor.cambio_cuenta'
VIGENCIA = timedelta(hours=24)


def pedir(request, actual, nueva):
    """Manda al correo del profesor el enlace para pasar de ``actual`` a ``nueva`` (sin guardar).

    Devuelve False si el correo no salio.
    """
    token = signing.dumps({'cuenta': actual.pk, 'version': actual.actualizada.isoformat(),
                           'banco': nueva.banco, 'tipo': nueva.tipo_cuenta,
                           'numero': bytes(nueva.numero_cifrado).decode()}, salt=SAL)
    user = actual.profesor.user
    return enviar('Confirma el cambio de tu cuenta bancaria', 'user_profesor/correo_cambio_cuenta.txt', {
        'nombre': user.first_name, 'banco': nueva.banco, 'enmascarado': nueva.enmascarado,
        'enlace': request.build_absolute_uri(reverse('confirmar_cambio_cuenta', args=[token])),
        'horas': int(VIGENCIA.total_seconds() // 3600),
    }, user.email)


def confirmar(profesor_id, token):
    """Aplica el cambio del enlace, avisa al correo y devuelve la cuenta.

    ValidationError si el enlace es falso, vencio, ya se uso o es de otro profesor.
    """
    try:
        datos = signing.loads(token, salt=SAL, max_age=VIGENCIA)
    except signing.BadSignature:  # incluye SignatureExpired
        raise ValidationError('El enlace no es válido o venció. Pide el cambio de nuevo.')
    cuenta = (CuentaBancaria.objects.select_related('profesor__user')
              .filter(pk=datos['cuenta'], profesor_id=profesor_id).first())
    if cuenta is None or cuenta.actualizada.isoformat() != datos['version']:
        raise ValidationError('El enlace ya se usó o la cuenta cambió después. Pide el cambio de nuevo.')

    cuenta.banco, cuenta.tipo_cuenta = datos['banco'], datos['tipo']
    cuenta.numero_cifrado = datos['numero'].encode()
    cuenta.ultimos_digitos = cuenta.numero[-4:]
    cuenta.cambiada_en = timezone.now()
    cuenta.save()

    user = cuenta.profesor.user
    enviar('Tu cuenta bancaria cambió', 'user_profesor/correo_cuenta_cambiada.txt', {
        'nombre': user.first_name, 'banco': cuenta.banco, 'enmascarado': cuenta.enmascarado,
        'pagable_desde': cuenta.pagable_desde,
    }, user.email)
    return cuenta
