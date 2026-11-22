"""LBW-11 / LBW-21: el escape de HTML en el JavaScript vive en un solo archivo (lbwus-utils.js).

Dos copias se desincronizan: si una se corrige, la otra queda con el hueco XSS. Estas pruebas fallan si aparece una
copia nueva, si una base de portal deja de cargar la utilidad, o si algun codigo cae a "sin escapar" cuando falta.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

RAIZ = Path(settings.BASE_DIR)
UTILIDAD = 'alumnos/static/alumnos/java/lbwus-utils.js'
# Bases que cargan lbwus-utils.js. Las demas la heredan: base_soporte y base_docente de base_admin, base_apoderado de
# base_alumno, legal_base de base.
BASES = (
    'alumnos/templates/alumnos/base.html',
    'alumnos/templates/alumnos/base_alumno.html',
    'admin_portal/templates/admin_portal/base_admin.html',
)
COPIA_DEL_ESCAPE = re.compile(r"replace\(/&/g|replace\(/\[&<>")
RESPALDO_SIN_ESCAPE = re.compile(r'window\.escaparHtml\s*(\?|\|\|)')


def archivos_propios(*sufijos):
    """HTML y JS del proyecto, sin librerias de terceros, sin lo recolectado y sin las pruebas."""
    for ruta in RAIZ.rglob('*'):
        partes = ruta.relative_to(RAIZ).parts
        if ruta.suffix not in sufijos or not ruta.is_file():
            continue
        if {'vendor', 'staticfiles', 'node_modules', 'tests', '.git'} & set(partes) or any(p.startswith('.venv') for p in partes):
            continue
        if ruta.name.endswith('.min.js'):
            continue
        yield ruta


class EscapeUnicoTests(SimpleTestCase):

    def test_solo_lbwus_utils_define_como_escapar_html(self):
        copias = [
            ruta.relative_to(RAIZ).as_posix() for ruta in archivos_propios('.html', '.js')
            if COPIA_DEL_ESCAPE.search(ruta.read_text(encoding='utf-8', errors='ignore'))
        ]
        self.assertEqual(copias, [UTILIDAD], 'el escape de HTML esta copiado: usa window.escaparHtml (lbwus-utils.js)')

    def test_cada_base_de_portal_carga_la_utilidad(self):
        for base in BASES:
            with self.subTest(base=base):
                self.assertIn('alumnos/java/lbwus-utils.js', (RAIZ / base).read_text(encoding='utf-8'))

    def test_nadie_cae_a_sin_escapar_si_falta_la_utilidad(self):
        """Un respaldo "window.escaparHtml || String" esconde que falta la carga y deja pasar el texto crudo."""
        con_respaldo = [
            ruta.relative_to(RAIZ).as_posix() for ruta in archivos_propios('.html', '.js')
            if RESPALDO_SIN_ESCAPE.search(ruta.read_text(encoding='utf-8', errors='ignore'))
        ]
        self.assertEqual(con_respaldo, [])
