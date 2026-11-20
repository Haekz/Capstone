"""Todas las rutas del proyecto, con argumentos de relleno, para pruebas de acceso (revision QA)."""

from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.converters import IntConverter, PathConverter, SlugConverter, StringConverter, UUIDConverter

RELLENO = {
    IntConverter: '999999',
    StringConverter: 'x',
    SlugConverter: 'x',
    PathConverter: 'x',
    UUIDConverter: '00000000-0000-0000-0000-000000000000',
}
# El admin de Django tiene su propio login y no lo usa el sitio.
PREFIJOS_FUERA = ('admin/',)


def _recorrer(patrones, prefijo='', espacio=''):
    for patron in patrones:
        texto = str(patron.pattern)
        if isinstance(patron, URLResolver):
            ns = f'{espacio}{patron.namespace}:' if patron.namespace else espacio
            yield from _recorrer(patron.url_patterns, prefijo + texto, ns)
        elif isinstance(patron, URLPattern):
            yield prefijo + texto, (espacio + patron.name) if patron.name else None, patron


def _con_relleno(ruta, patron):
    """'/alumnos/<int:pk>/' -> '/alumnos/999999/'. None si la ruta es una expresion regular."""
    convertidores = getattr(patron.pattern, 'converters', {})
    if '(?P<' in ruta or '^' in ruta or '\\' in ruta:
        return None
    for nombre, conv in convertidores.items():
        for etiqueta in (f'<{nombre}>', *(f'<{t}:{nombre}>' for t in ('int', 'str', 'slug', 'path', 'uuid'))):
            ruta = ruta.replace(etiqueta, RELLENO.get(type(conv), 'x'))
    return '/' + ruta


def rutas():
    """[(url con relleno, nombre, tiene_argumentos)] de todo el proyecto, sin el admin de Django."""
    vistas = []
    for ruta, nombre, patron in _recorrer(get_resolver().url_patterns):
        if ruta.startswith(PREFIJOS_FUERA):
            continue
        url = _con_relleno(ruta, patron)
        if url is not None:
            vistas.append((url, nombre, '<' in ruta))
    return vistas
