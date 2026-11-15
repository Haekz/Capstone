"""Lo basico para buscadores y vistas previas (Google, WhatsApp): direccion canonica, robots.txt y sitemap.xml.

Todo usa settings.SITIO_URL y no el dominio por el que se entro: el sitio tambien responde en *.up.railway.app y ahi
la direccion canonica debe seguir siendo lbwus.xyz. Un Disallow en robots.txt no protege nada (las pantallas privadas
piden sesion igual): solo evita que los buscadores pierdan tiempo en ellas.
"""
from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import escape
from django.views.decorators.http import require_safe

RUTAS_PRIVADAS = ('/admin/', '/admin_portal/', '/profesor/', '/soporte/', '/apoderados/', '/comunidad/', '/resenas/',
                  '/mensajes/', '/notificaciones/', '/agenda/', '/observaciones/', '/requerimientos/', '/accounts/',
                  '/puerta/', '/salud/')
PAGINAS_PUBLICAS = ('home', 'nosotros', 'servicios', 'planes', 'contactos')  # nombres de url


def sitio(request):
    """Procesador de contexto: SITIO_URL para el canonical y Open Graph de las plantillas."""
    return {'SITIO_URL': settings.SITIO_URL}


@require_safe
def robots(request):
    lineas = ['User-agent: *', *(f'Disallow: {ruta}' for ruta in RUTAS_PRIVADAS), '',
              f'Sitemap: {settings.SITIO_URL}/sitemap.xml']
    return HttpResponse('\n'.join(lineas) + '\n', content_type='text/plain; charset=utf-8')


@require_safe
def sitemap(request):
    direcciones = ''.join(f'<url><loc>{escape(settings.SITIO_URL + reverse(nombre))}</loc></url>'
                          for nombre in PAGINAS_PUBLICAS)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{direcciones}</urlset>')
    return HttpResponse(xml, content_type='application/xml; charset=utf-8')
