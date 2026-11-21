"""El verde --ok (claro) se lee en los 5 portales: 4,5:1 sobre blanco y en un chip --ok-soft sobre el fondo lila de la
pagina (WCAG 1.4.3). Con #0f8a60 daba 4,35:1 y 3,55:1; medido en el navegador el 21-nov (ok_medir_contraste.py, fuera del
repo). El token esta repetido en cada portal: estas pruebas tambien impiden que las copias se separen.
"""

import re

from django.test import SimpleTestCase

from tests.test_planes_en_portal import _contraste, _leer

TOKENS = {  # portal: hoja que define --ok (la primera definicion es la del tema claro)
    'alumno y apoderado': 'alumnos/static/alumnos/css/alumn_1/13_pulido.css',
    'docente': 'user_profesor/static/user_profesor/panel/06a_pulido_docente_marco.css',
    'admin': 'admin_portal/static/admin_portal/css/admin_panel/06a_pulido_admin_marco.css',
    'soporte': 'admin_portal/static/admin_portal/css/admin_panel/07a_pulido_soporte_marco.css',
}
FONDO_PAGINA = '#f6f5fa'  # fondo de la pagina en claro, medido en el navegador


def _claro(css, variable):
    return re.search(rf'{variable}:\s*([^;]+);', css).group(1).strip()


def _sobre(rgba, fondo):
    """Color hexadecimal de ``rgba(r, g, b, a)`` pintado sobre ``fondo``."""
    *color, alfa = (float(v) for v in re.findall(r'[\d.]+', rgba))
    base = [int(fondo.lstrip('#')[i:i + 2], 16) for i in (0, 2, 4)]
    return '#' + ''.join(f'{round(c * alfa + b * (1 - alfa)):02x}' for c, b in zip(color, base))


class ContrasteDelVerdeOkTests(SimpleTestCase):

    def test_se_lee_sobre_blanco_y_en_su_chip_en_cada_portal(self):
        for portal, hoja in TOKENS.items():
            css = _leer(hoja)
            ok, chip = _claro(css, '--ok'), _sobre(_claro(css, '--ok-soft'), FONDO_PAGINA)
            with self.subTest(portal=portal):
                self.assertGreaterEqual(_contraste(ok, '#ffffff'), 4.5)
                self.assertGreaterEqual(_contraste(ok, chip), 4.5)

    def test_los_cinco_portales_usan_el_mismo_verde(self):
        self.assertEqual(len({_claro(_leer(hoja), '--ok') for hoja in TOKENS.values()}), 1)

    def test_el_vencimiento_de_la_tarjeta_blanca_usa_ese_verde(self):
        # La tarjeta de clases del banner es blanca tambien en oscuro: lleva el verde claro fijo, no var(--ok).
        css = _leer(TOKENS['alumno y apoderado'])
        regla = re.search(r'#portal-alumno \.tc-vence \{([^}]*)\}', css).group(1)
        self.assertEqual(_claro(regla, 'color'), _claro(css, '--ok'))
