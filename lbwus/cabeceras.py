"""Cabeceras de seguridad: Content-Security-Policy y Permissions-Policy (SCRUM-93).

La CSP va en modo Report-Only: el navegador no bloquea nada, solo avisa en la
consola. Para hacerla obligatoria se define CSP_OBLIGATORIA=1
(docs/CONFIGURACION_PRODUCCION.md, seccion 7).

Los origenes salen de recorrer plantillas, JS y CSS (reporte en .ia/reportes/cabeceras.md).
Si agregas un CDN, un iframe o un fetch a otro dominio, agregalo aqui.
"""

from django.conf import settings

JITSI = 'https://meet.jit.si'
TRANSBANK = ('https://webpay3gint.transbank.cl', 'https://webpay3g.transbank.cl')  # integracion y produccion

# 'unsafe-inline' es temporal: hay <script>, onclick= y style= en linea en las plantillas.
CSP = {
    'default-src': ("'self'",),
    'script-src': ("'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', JITSI),
    'style-src': ("'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com',
                  'https://fonts.googleapis.com'),
    'font-src': ("'self'", 'data:', 'https://cdn.jsdelivr.net', 'https://cdnjs.cloudflare.com',
                 'https://fonts.gstatic.com'),
    'img-src': ("'self'", 'data:', 'https://commondatastorage.googleapis.com'),
    'media-src': ("'self'", 'https://commondatastorage.googleapis.com'),
    'connect-src': ("'self'", JITSI, 'wss://meet.jit.si'),
    'frame-src': (JITSI, 'https://www.google.com'),  # sala virtual y mapa de home.html
    # Webpay recibe un POST (redirect_webpay.html); Google responde con un redirect tras el POST de allauth.
    'form-action': ("'self'", *TRANSBANK, 'https://accounts.google.com'),
    # En Report-Only los navegadores ignoran frame-ancestors: hasta hacerla obligatoria,
    # protege X-Frame-Options: DENY (XFrameOptionsMiddleware).
    'frame-ancestors': ("'none'",),
    'object-src': ("'none'",),
    'base-uri': ("'self'",),
}

# Camara, microfono, pantalla y pantalla completa: la pagina y el iframe de Jitsi
# (la sala usa los botones microphone, camera, desktop y fullscreen). El resto, nadie.
PERMISOS = {
    'camera': ('self', JITSI),
    'microphone': ('self', JITSI),
    'display-capture': ('self', JITSI),
    'fullscreen': ('self', JITSI),
    'geolocation': (),
    'payment': (),
    'usb': (),
    'serial': (),
    'bluetooth': (),
    'hid': (),
    'midi': (),
    'accelerometer': (),
    'gyroscope': (),
    'magnetometer': (),
    'browsing-topics': (),
}


def politica_csp():
    return '; '.join(f"{directiva} {' '.join(origenes)}" for directiva, origenes in CSP.items())


def politica_permisos():
    def lista(origenes):
        return ' '.join(o if o == 'self' else f'"{o}"' for o in origenes)
    return ', '.join(f'{permiso}=({lista(origenes)})' for permiso, origenes in PERMISOS.items())


class CabecerasSeguridadMiddleware:
    """Agrega las dos cabeceras a toda respuesta, salvo que la vista ya las haya puesto."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = politica_csp()
        self.permisos = politica_permisos()

    def __call__(self, request):
        response = self.get_response(request)
        nombre = ('Content-Security-Policy' if settings.CSP_OBLIGATORIA
                  else 'Content-Security-Policy-Report-Only')
        response.headers.setdefault(nombre, self.csp)
        response.headers.setdefault('Permissions-Policy', self.permisos)
        return response
