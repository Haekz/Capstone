"""Ayudas de pruebas para vigilar variables CSS.

Una var(--x) que no esta definida NO da error: la propiedad queda sin valor (fondo transparente, color heredado, borde
invisible). Por eso se vigila con una prueba: cada variable usada debe estar definida en algun archivo que la pagina carga.
"""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def leer(ruta):
    """Texto de un archivo del proyecto, dada su ruta relativa a la raiz."""
    return (RAIZ / ruta).read_text(encoding='utf-8')


def definidas(texto):
    return set(re.findall(r'(--[\w-]+)\s*:', texto))


def usadas(texto):
    return set(re.findall(r'var\((--[\w-]+)', texto))


def sin_definir(archivos, definidas_en=()):
    """{archivo: [variables usadas que nadie define]} para los `archivos` revisados.

    Cuenta como definida la que esta en alguno de `definidas_en` o en el propio archivo (estilos en linea o <style>).
    """
    disponibles = set()
    for ruta in definidas_en:
        disponibles |= definidas(leer(ruta))

    faltantes = {}
    for ruta in archivos:
        texto = leer(ruta)
        faltan = usadas(texto) - disponibles - definidas(texto)
        if faltan:
            faltantes[ruta] = sorted(faltan)
    return faltantes
