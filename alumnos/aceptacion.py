"""Aceptacion de los Terminos y la Politica de privacidad al comprar un paquete.

Quien compra debe haber aceptado la VERSION vigente de los textos. Si ya la acepto (una compra anterior), no se le
vuelve a pedir; si cambian los textos, `VERSION` sube y se le pide una vez mas. El unico punto de control es
`webpay.iniciar_compra_paquete`, por donde pasan el alumno y el apoderado.
"""

from .models.aceptacion import AceptacionLegal

# Fecha de actualizacion de /terminos/ y /privacidad/ (la muestran ambas paginas). Cambiarla pide aceptar de nuevo.
VERSION = '26 de noviembre de 2026'  # Privacidad: los videos pasan de MongoDB Atlas a Cloudflare R2
CAMPO = 'acepta_terminos'  # nombre de la casilla en el formulario de compra


def pendiente(user):
    """True si `user` aun no acepto la version vigente."""
    return not AceptacionLegal.objects.filter(user=user, version=VERSION).exists()


def confirmar(request):
    """True si quien compra ya acepto la version vigente o la acepta ahora (casilla marcada); False si falta."""
    if not pendiente(request.user):
        return True
    if request.POST.get(CAMPO) != '1':
        return False
    AceptacionLegal.objects.get_or_create(user=request.user, version=VERSION)
    return True
