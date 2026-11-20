"""Credenciales de Transbank (S-08 / 7.6): integracion por defecto, produccion solo si esta completa.

Lo usan settings.py (al arrancar) y alumnos.webpay._tx (en cada pago, por si se cambia la configuracion en
caliente o en pruebas). No importa modelos: settings.py lo carga antes que las apps.
"""

from django.core.exceptions import ImproperlyConfigured


def validar_produccion(habilitada, ambiente, codigo_comercio, llave):
    """Con produccion habilitada, cualquier dato faltante es un error y no una vuelta a integracion.

    Antes, si faltaba algo, se usaba el ambiente de pruebas en silencio: el sitio aceptaba tarjetas de
    prueba y regalaba clases.
    """
    if not habilitada:
        return
    requisitos = (
        ('TRANSBANK_ENVIRONMENT=LIVE', ambiente == 'LIVE'),
        ('TRANSBANK_COMMERCE_CODE', codigo_comercio),
        ('TRANSBANK_API_KEY', llave),
    )
    faltan = [nombre for nombre, cumple in requisitos if not cumple]
    if faltan:
        raise ImproperlyConfigured(
            f'TRANSBANK_PRODUCCION_HABILITADA=True, pero falta: {", ".join(faltan)}. '
            'No se arranca para no cobrar con el ambiente de pruebas.')
